from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from api import app
from domain import DeclaredBodyData, BodyMeasurements
from estimation import EstimateMeasurements, MAX_PHOTO_BYTES


def picture(size=(600, 1000), metadata=False):
    output = BytesIO()
    exif = Image.Exif()
    if metadata:
        exif[270] = "private-test-metadata"
        exif[274] = 6
    Image.new("RGB", size, "#e5daf4").save(output, "JPEG", exif=exif)
    return output.getvalue()


@pytest.mark.parametrize("height,weight", [(129, 70), (170, 251), (float("nan"), 70),
                                           (170, float("inf")), (True, 70)])
def test_declared_data_limits(height, weight):
    with pytest.raises(ValueError):
        DeclaredBodyData(height, weight)


def test_orientation_and_metadata_removed_before_estimator():
    class Estimator:
        def estimate(self, request):
            assert request.declared == DeclaredBodyData(170, 68)
            assert (request.width, request.height) == (1000, 600)
            with Image.open(BytesIO(request.image)) as image:
                assert not image.getexif()
                assert "exif" not in image.info
                assert image.format == "JPEG"
            return BodyMeasurements(170, 40, 92, 78, 96)

    result = EstimateMeasurements(Estimator()).execute(DeclaredBodyData(170, 68), picture(metadata=True), "image/jpeg")
    assert result.height == 170


@pytest.mark.parametrize("data,content_type", [(b"not a photo", "image/jpeg"),
                                               (picture(), "image/png"),
                                               (picture((100, 100)), "image/jpeg"),
                                               (b"<svg/>", "image/svg+xml")])
def test_invalid_photos_never_reach_estimator(data, content_type):
    class Estimator:
        def estimate(self, request):
            pytest.fail("invalid photo reached estimator")
    with pytest.raises(ValueError):
        EstimateMeasurements(Estimator()).execute(DeclaredBodyData(170, 68), data, content_type)


def test_pending_model_has_no_fake_measurements_or_files():
    from api import ROOT
    before = set((ROOT / "output").iterdir())
    with TestClient(app) as client:
        response = client.post("/api/estimations", data={"height_cm": "170", "weight_kg": "68"},
                               files={"photo": ("photo.jpg", picture(), "image/jpeg")})
        assert response.status_code == 503
        assert response.json()["error"] == "sam_access_pending"
        assert response.json()["photoRetained"] is False
        assert "measurements" not in response.json()
        assert set((ROOT / "output").iterdir()) == before


def test_api_rejects_invalid_data_and_large_streams():
    with TestClient(app) as client:
        fields = {"height_cm": "170", "weight_kg": "68"}
        for values in [fields | {"height_cm": "nan"}, fields | {"weight_kg": "0"}]:
            assert client.post("/api/estimations", data=values,
                               files={"photo": ("x.jpg", picture(), "image/jpeg")}).status_code == 422
        assert client.post("/api/estimations", data=fields,
                           files={"photo": ("x.jpg", b"bad", "image/jpeg")}).status_code == 422
        # No Content-Length: enforce the cap on actual streamed bytes as well.
        def chunks():
            for _ in range(10):
                yield b"x" * (1024 * 1024)
        response = client.post("/api/estimations", content=chunks(),
                               headers={"Content-Type": "multipart/form-data; boundary=test"})
        assert response.status_code == 413
        response = client.post("/api/estimations", data=fields,
                               files={"photo": ("large.jpg", b"x" * (MAX_PHOTO_BYTES + 1), "image/jpeg")})
        assert response.status_code == 413
