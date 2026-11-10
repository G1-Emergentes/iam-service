"""Loopback-only mobile development API. No public authorization or anthropometry."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
import subprocess
import json
import sys
from tempfile import TemporaryDirectory
from threading import Lock, Timer
import time
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from estimation import MAX_PHOTO_BYTES, EstimateMeasurements
from domain import DeclaredBodyData
from sam.avatar_store import identity, AvatarStore
from sam.body_geometry import validate_measurements
from pydantic import BaseModel, ConfigDict


class PreparedPhoto:
    def estimate(self, request):
        return request.image


def reconstruct(photo):
    # TemporaryDirectory removes the photo and intermediate results even on failure.
    with TemporaryDirectory(prefix="mirage-sam-") as directory:
        path = Path(directory)
        payload = photo if isinstance(photo, dict) else {'photo': photo, 'height': 170}
        (path / "input.jpg").write_bytes(payload.get('photo') or b'')
        if 'recipe' in payload:
            (path / 'body.json').write_text(json.dumps(payload['recipe']), encoding='utf-8')
            command = [sys.executable, str(ROOT / 'sam/body_geometry.py'), '--recipe', str(path / 'body.json'),
                       '--output', str(path / 'reconstruction.glb')]
        else:
            command = [sys.executable, str(ROOT / "sam/probe.py"), "--image", str(path / "input.jpg"),
                       "--output", str(path), "--private", '--height-cm', str(payload['height'])]
        result = subprocess.run(
            command, capture_output=True, timeout=180)
        if result.returncode:
            raise RuntimeError("reconstruction_failed")
        model = (path / "reconstruction.glb").read_bytes()
        if model[:4] != b"glTF":
            raise RuntimeError("invalid_model")
        return {'model': model, 'body': json.loads((path / 'body.json').read_text(encoding='utf-8')),
                'photo': payload.get('photo'), 'photo_path': payload.get('photo_path')}


class Jobs:
    def __init__(self, runner=reconstruct):
        self.runner = runner
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.lock = Lock()
        self.jobs = {}
        self.timers = []

    def submit(self, photo, owner=None):
        with self.lock:
            now = time.monotonic()
            self.jobs = {k: v for k, v in self.jobs.items() if v["expires"] > now}
            if len(self.jobs) >= 2:
                raise HTTPException(429, "local_capacity_full")
            key = str(uuid4())
            self.jobs[key] = {"status": "queued", "expires": now + 600, 'owner': owner}
        self.pool.submit(self.run, key, photo)
        timer = Timer(600, self.expire, args=(key,))
        timer.daemon = True
        self.timers = [item for item in self.timers if item.is_alive()] + [timer]
        timer.start()
        return key

    def expire(self, key):
        with self.lock:
            self.jobs.pop(key, None)

    def close(self):
        for timer in self.timers:
            timer.cancel()
        self.pool.shutdown(wait=True)
        self.jobs.clear()

    def run(self, key, photo):
        with self.lock:
            if key not in self.jobs:
                return
            self.jobs[key]["status"] = "running"
        try:
            model = self.runner(photo)
            with self.lock:
                if key in self.jobs:
                    self.jobs[key].update(status="succeeded", **(model if isinstance(model, dict) else {'model': model}))
        except Exception:
            with self.lock:
                if key in self.jobs:
                    self.jobs[key]["status"] = "failed"

    def get(self, key):
        with self.lock:
            job = self.jobs.get(str(key))
            if not job or job["expires"] <= time.monotonic():
                raise HTTPException(404, "job_expired")
            return dict(job)


@asynccontextmanager
async def lifespan(app):
    app.state.jobs = Jobs()
    yield
    app.state.jobs.close()


app = FastAPI(title="Mirage SAM · local mobile", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "10.0.2.2", "testserver"])


class UploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        total = 0
        async def bounded_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > MAX_PHOTO_BYTES + 64 * 1024:
                raise HTTPException(413, "photo_too_large")
            return message
        await self.app(scope, bounded_receive, send)


app.add_middleware(UploadLimit)


@app.middleware("http")
async def local_only(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        return Response(status_code=403)
    response = await call_next(request)
    response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                             "Referrer-Policy": "no-referrer"})
    return response


@app.get("/health")
def health():
    return {"status": "ok", "mode": "local-reconstruction", "measurementsValidated": False}


@app.post("/api/reconstructions", status_code=202)
async def submit(request: Request, photo: UploadFile = File(),
                 height_cm: float = Form(), weight_kg: float = Form()):
    try:
        data = await photo.read(MAX_PHOTO_BYTES + 1)
        clean = EstimateMeasurements(PreparedPhoto()).execute(
            DeclaredBodyData(height_cm, weight_kg), data, photo.content_type)
        user = identity(request)[0] if request.headers.get('authorization') else None
        key = request.app.state.jobs.submit({'photo': clean, 'height': height_cm}, owner=user)
        return {"id": key}
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    finally:
        await photo.close()


@app.get("/api/reconstructions/{key}")
def status(key: UUID, request: Request):
    job = request.app.state.jobs.get(key)
    return {"id": str(key), "status": job["status"], "measurementsValidated": False, 'body': job.get('body')}


@app.get("/api/reconstructions/{key}/model.glb")
def model(key: UUID, request: Request):
    job = request.app.state.jobs.get(key)
    if job["status"] != "succeeded":
        raise HTTPException(409, "model_not_ready")
    return Response(job["model"], media_type="model/gltf-binary")


@app.delete("/api/reconstructions/{key}", status_code=204)
def discard(key: UUID, request: Request):
    jobs = request.app.state.jobs
    with jobs.lock:
        job = jobs.jobs.get(str(key))
        if job and job["status"] in ("succeeded", "failed"):
            del jobs.jobs[str(key)]
    return Response(status_code=204)


@app.get("/view/{key}", response_class=HTMLResponse)
def view(key: UUID, request: Request):
    request.app.state.jobs.get(key)
    return (ROOT / "sam/view.html").read_text(encoding="utf-8").replace("JOB_ID", str(key))


@app.get("/assets/{name}")
def asset(name: str):
    if name not in {"babylon.js", "babylonjs.loaders.min.js"}:
        raise HTTPException(404)
    return FileResponse(ROOT / "static" / name)


class BodyEdit(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    measurements: dict[str, float | None]
    fitPreference: str = 'Regular'


def owned_job(request, key):
    user, bearer = identity(request)
    job = request.app.state.jobs.get(key)
    if job.get('owner') != user:
        raise HTTPException(403, 'avatar_access_denied')
    if job['status'] != 'succeeded' or not job.get('body'):
        raise HTTPException(409, 'body_not_ready')
    return user, bearer, job


def edit_recipe(job, body):
    try:
        validate_measurements(body.measurements)
        if body.fitPreference not in ('Fitted', 'Regular', 'Oversized'):
            raise ValueError('invalid_fit_preference')
    except ValueError as error:
        raise HTTPException(422, str(error))
    return {**job['body'], 'measurements': body.measurements, 'fitPreference': body.fitPreference}


@app.post('/api/reconstructions/{key}/adjust', status_code=202)
def adjust(key: UUID, body: BodyEdit, request: Request):
    user, _, job = owned_job(request, key)
    recipe = edit_recipe(job, body)
    return {'id': request.app.state.jobs.submit({'recipe': recipe, 'photo': job.get('photo'),
                'photo_path': job.get('photo_path')}, owner=user)}


@app.put('/api/reconstructions/{key}/profile')
def save(key: UUID, body: BodyEdit, request: Request):
    user, bearer, job = owned_job(request, key)
    recipe = edit_recipe(job, body)
    store = AvatarStore(user, bearer)
    path = store.save(recipe, job.get('photo'), body.fitPreference, job.get('photo_path'))
    with request.app.state.jobs.lock:
        if str(key) in request.app.state.jobs.jobs:
            request.app.state.jobs.jobs[str(key)]['photo_path'] = path
    return {'saved': True, 'fitPreference': body.fitPreference}


@app.post('/api/avatar/open', status_code=202)
def open_saved(request: Request):
    user, bearer = identity(request)
    saved = AvatarStore(user, bearer).get()
    if saved is None:
        raise HTTPException(404, 'no_saved_avatar')
    key = request.app.state.jobs.submit({'recipe': saved['body'], 'photo_path': saved['photo_path']}, owner=user)
    return {'id': key, 'fitPreference': saved['fit_preference']}


@app.get('/api/avatar/photo')
def saved_photo(request: Request):
    user, bearer = identity(request)
    store = AvatarStore(user, bearer)
    saved = store.get()
    if saved is None:
        raise HTTPException(404, 'no_saved_avatar')
    return Response(store.photo(saved['photo_path']), media_type='image/jpeg')
