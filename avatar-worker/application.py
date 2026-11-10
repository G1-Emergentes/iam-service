"""Single local worker with a bounded queue and durable result metadata."""
from concurrent.futures import ThreadPoolExecutor
import json
import logging
from pathlib import Path
from threading import Lock, BoundedSemaphore
from uuid import uuid4

from domain import BodyMeasurements


class AvatarJobs:
    def __init__(self, directory: Path, engine_factory):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.engine_factory = engine_factory
        self.engine = None
        self.lock = Lock()
        self.capacity = BoundedSemaphore(2)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="avatar")
        self.jobs = {}
        for path in directory.glob("*.json"):
            job = json.loads(path.read_text(encoding="utf-8"))
            if job["status"] in ("pending", "running"):
                job.update(status="failed", error="worker_restarted")
                self._save(job)
            self.jobs[job["id"]] = job

    def _save(self, job):
        path = self.directory / (job["id"] + ".json")
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)

    def submit(self, measurements: BodyMeasurements):
        if not self.capacity.acquire(blocking=False):
            raise RuntimeError("worker_busy")
        job = {"id": str(uuid4()), "status": "pending", "measurements": measurements.to_dict()}
        try:
            with self.lock:
                self._save(job)
                self.jobs[job["id"]] = job
            self.executor.submit(self._run, job["id"], measurements)
        except Exception:
            self.capacity.release()
            raise
        return job.copy()

    def get(self, job_id):
        with self.lock:
            job = self.jobs.get(str(job_id))
            return job.copy() if job else None

    def _update(self, job_id, **values):
        with self.lock:
            job = self.jobs[job_id].copy()
            job.update(values)
            self._save(job)
            self.jobs[job_id] = job

    def _run(self, job_id, measurements):
        try:
            self._update(job_id, status="running")
            if self.engine is None:
                self.engine = self.engine_factory()
            result = self.engine.generate(measurements, self.directory / (job_id + ".glb"))
            self._update(job_id, status="succeeded", result=result,
                         modelUrl=f"/api/jobs/{job_id}/model.glb")
        except Exception:
            logging.exception("Avatar generation failed for job %s", job_id)
            self._update(job_id, status="failed", error="generation_failed")
        finally:
            self.capacity.release()

    def close(self):
        self.executor.shutdown(wait=True)
