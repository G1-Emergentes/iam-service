import json
from threading import Event
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api import app
from application import AvatarJobs
from domain import BodyMeasurements

SAMPLE = BodyMeasurements(170, 40, 92, 78, 96)


def await_finished(jobs, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = jobs.get(job_id)
        if result["status"] in ("succeeded", "failed"):
            return result
        time.sleep(.01)
    raise AssertionError("job did not finish")


@pytest.mark.parametrize("name,value", [("height", float("nan")), ("waist", float("inf")),
                                        ("hip", -5), ("height", 100), ("chest", True), ("waist", "78")])
def test_invalid_measurements(name, value):
    with pytest.raises(ValueError):
        BodyMeasurements(**(SAMPLE.to_dict() | {name: value}))


def test_queue_bounded_and_results_survive_restart(tmp_path):
    started, release = Event(), Event()

    class Engine:
        def generate(self, body, path):
            started.set()
            assert release.wait(5)
            path.write_bytes(b"glTF-test")
            return {"approximate": True}

    jobs = AvatarJobs(tmp_path, Engine)
    try:
        first = jobs.submit(SAMPLE)
        assert started.wait(5)
        second = jobs.submit(SAMPLE)
        with pytest.raises(RuntimeError, match="worker_busy"):
            jobs.submit(SAMPLE)
        release.set()
        assert await_finished(jobs, first["id"])["status"] == "succeeded"
        assert await_finished(jobs, second["id"])["status"] == "succeeded"
    finally:
        release.set()
        jobs.close()
    restored = AvatarJobs(tmp_path, Engine)
    try:
        assert restored.get(first["id"])["status"] == "succeeded"
    finally:
        restored.close()


def test_interrupted_and_failed_jobs_are_explicit(tmp_path):
    interrupted = {"id": str(uuid4()), "status": "running"}
    (tmp_path / (interrupted["id"] + ".json")).write_text(json.dumps(interrupted))

    class BrokenEngine:
        def generate(self, body, path):
            raise ValueError("test_failure")

    jobs = AvatarJobs(tmp_path, BrokenEngine)
    try:
        assert jobs.get(interrupted["id"])["error"] == "worker_restarted"
        job = jobs.submit(SAMPLE)
        assert await_finished(jobs, job["id"])["error"] == "generation_failed"
    finally:
        jobs.close()


def test_api_validation_and_browser_isolation(tmp_path):
    with TestClient(app) as client:
        original = app.state.jobs
        jobs = AvatarJobs(tmp_path, lambda: None)
        app.state.jobs = jobs
        try:
            assert client.get("/health").status_code == 200
            assert client.post("/api/jobs", json=SAMPLE.to_dict(), headers={"Origin": "https://other.example"}).status_code == 403
            assert client.get("/health", headers={"Host": "attacker.example"}).status_code == 400
            assert client.post("/api/jobs", json=SAMPLE.to_dict() | {"height": True}).status_code == 422
            assert client.post("/api/jobs", json=SAMPLE.to_dict() | {"token": "unexpected"}).status_code == 422
            assert client.get("/api/jobs/" + str(uuid4())).status_code == 404
            assert client.get("/api/jobs/not-a-uuid/model.glb").status_code == 422
            assert client.get("/assets/domain.py").status_code == 404
        finally:
            app.state.jobs = original
            jobs.close()
