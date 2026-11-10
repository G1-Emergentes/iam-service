"""Local prototype only. Public account authorization stays in Drogon."""
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.middleware.trustedhost import TrustedHostMiddleware

from application import AvatarJobs
from domain import BodyMeasurements, DeclaredBodyData
from estimation import EstimateMeasurements, SamBodyEstimator, EstimatorUnavailable, MAX_PHOTO_BYTES

ROOT = Path(__file__).resolve().parent


def create_engine():
    from mesh_engine import AnnyMeshEngine
    return AnnyMeshEngine()


@asynccontextmanager
async def lifespan(app):
    app.state.jobs = AvatarJobs(ROOT / "output", create_engine)
    app.state.estimations = EstimateMeasurements(SamBodyEstimator())
    yield
    app.state.jobs.close()


app = FastAPI(title="Mirage · Avatar local prototype", version="0.1.0", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])


class UploadLimit:
    """Bound the complete multipart stream before the parser can spool large files."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/api/estimations":
            return await self.app(scope, receive, send)
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
async def local_browser_access(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        return JSONResponse({"detail": "cross_origin_access_denied"}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


class MeasurementsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    height: float
    shoulderWidth: float
    chest: float
    waist: float
    hip: float


@app.get("/health")
def health():
    return {"status": "ok", "mode": "local-prototype"}


@app.post("/api/estimations", responses={503: {"description": "SAM model access pending"}})
def estimate(request: Request, photo: UploadFile = File(),
             height_cm: float = Form(), weight_kg: float = Form()):
    try:
        declared = DeclaredBodyData(height_cm, weight_kg)
        data = photo.file.read(MAX_PHOTO_BYTES + 1)
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(413, "photo_too_large")
        measurements = request.app.state.estimations.execute(declared, data, photo.content_type)
        return {"status": "estimated", "measurements": measurements.to_dict(),
                "requiresConfirmation": True}
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except EstimatorUnavailable:
        return JSONResponse({"status": "unavailable", "error": "sam_access_pending",
                             "message": "Estimación por foto pendiente de habilitación.",
                             "photoRetained": False}, status_code=503)
    finally:
        photo.file.close()


@app.post("/api/jobs", status_code=202)
def generate(body: MeasurementsInput, request: Request):
    try:
        measurements = BodyMeasurements(**body.model_dump())
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    try:
        return request.app.state.jobs.submit(measurements)
    except RuntimeError as error:
        raise HTTPException(429, "worker_busy") from error


def find_job(request, job_id):
    job = request.app.state.jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "job_not_found")
    return job


@app.get("/api/jobs/{job_id}")
def get_job(job_id: UUID, request: Request):
    return find_job(request, job_id)


@app.get("/api/jobs/{job_id}/model.glb")
def download_model(job_id: UUID, request: Request):
    job = find_job(request, job_id)
    if job["status"] != "succeeded":
        raise HTTPException(409, "model_not_ready")
    return FileResponse(ROOT / "output" / (str(job_id) + ".glb"), media_type="model/gltf-binary")


@app.get("/")
def preview():
    return FileResponse(ROOT / "static/index.html")


@app.get("/assets/{name}", include_in_schema=False)
def asset(name: str):
    allowed = {"preview.js", "capture.js", "preview.css", "babylon.js", "babylonjs.loaders.min.js"}
    if name not in allowed:
        raise HTTPException(404)
    return FileResponse(ROOT / "static" / name)
