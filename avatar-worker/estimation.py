"""Photo preparation and the estimator boundary; never substitute invented measures."""
from io import BytesIO
from typing import Protocol
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from domain import DeclaredBodyData, PhotoEstimationRequest, BodyMeasurements

MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 20_000_000


class EstimatorUnavailable(Exception):
    pass


class BodyEstimator(Protocol):
    def estimate(self, request: PhotoEstimationRequest) -> BodyMeasurements: ...


class SamBodyEstimator:
    def estimate(self, request: PhotoEstimationRequest) -> BodyMeasurements:
        # SAM checkpoints require approved access; no fallback to synthetic estimates.
        raise EstimatorUnavailable("sam_access_pending")


class EstimateMeasurements:
    def __init__(self, estimator: BodyEstimator):
        self.estimator = estimator

    def execute(self, declared: DeclaredBodyData, data: bytes, content_type: str):
        if not data or len(data) > MAX_PHOTO_BYTES:
            raise ValueError("photo_size_invalid")
        formats = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
        expected = formats.get(content_type)
        if expected is None:
            raise ValueError("photo_format_unsupported")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as image:
                    if image.format != expected or getattr(image, "n_frames", 1) != 1:
                        raise ValueError("photo_format_invalid")
                    if min(image.size) < 256 or image.width * image.height > MAX_PIXELS:
                        raise ValueError("photo_dimensions_invalid")
                    image.verify()
                with Image.open(BytesIO(data)) as image:
                    # Apply orientation, then rebuild pixels to discard EXIF/GPS metadata.
                    oriented = ImageOps.exif_transpose(image).convert("RGB")
                    oriented.thumbnail((2560, 2560))
                    clean = Image.new("RGB", oriented.size)
                    clean.paste(oriented)
                    output = BytesIO()
                    clean.save(output, format="JPEG", quality=90)
                    request = PhotoEstimationRequest(declared, output.getvalue(), *clean.size)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
                Image.DecompressionBombWarning) as error:
            raise ValueError("photo_decode_failed") from error
        return self.estimator.estimate(request)
