"""Isolated SAM inference check. Does not estimate centimetres or update profiles."""
import argparse
import json
import os
import shutil
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".sam-source"
os.environ.setdefault("WANDB_MODE", "disabled")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("MOMENTUM_ENABLED", "0")
sys.path.insert(0, str(SOURCE))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, default=SOURCE / "assets/qualitative_comparisons/sample1/input_bbox.png")
    parser.add_argument("--output", type=Path, default=ROOT / "output/sam-probe")
    parser.add_argument("--private", action="store_true", help="Do not retain photos, raw predictions or preview assets")
    parser.add_argument("--height-cm", type=float)
    args = parser.parse_args()

    import cv2
    import numpy as np
    import torch
    import trimesh
    from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available in this isolated environment")
    image = cv2.imread(str(args.image))
    if image is None:
        raise ValueError("Cannot decode input image")
    torch.set_num_threads(4)
    torch.cuda.reset_peak_memory_stats()
    free_before, total = torch.cuda.mem_get_info()
    started = time.perf_counter()
    weights = ROOT / "models/sam-3d-body-vith"
    model, config = load_sam_3d_body(checkpoint_path=str(weights / "model.ckpt"),
                                    mhr_path=str(weights / "assets/mhr_model.pt"), device="cuda")
    torch.cuda.synchronize()
    loaded = time.perf_counter()
    estimator = SAM3DBodyEstimator(model, config, human_detector=None,
                                  human_segmentor=None, fov_estimator=None)
    with torch.inference_mode():
        predictions = estimator.process_one_image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), inference_type="body")
    torch.cuda.synchronize()
    finished = time.perf_counter()
    if len(predictions) != 1:
        raise RuntimeError("Expected exactly one body reconstruction")
    result = predictions[0]
    vertices = result["pred_vertices"]
    faces = estimator.faces
    assert vertices.ndim == 2 and vertices.shape[1] == 3 and len(vertices) > 1000
    assert np.isfinite(vertices).all()
    assert faces.ndim == 2 and faces.shape[1] == 3 and faces.min() >= 0 and faces.max() < len(vertices)
    assert np.all(np.ptp(vertices, axis=0) > 0)
    args.output.mkdir(parents=True, exist_ok=True)
    # Preserve raw pose/shape for subsequent calibration; never use display geometry as a body measurement.
    if not args.private:
        np.savez_compressed(args.output / "prediction.npz", **{k: v for k, v in result.items() if isinstance(v, np.ndarray)}, faces=faces)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    mesh.vertices[:, 0] -= mesh.vertices[:, 0].mean()
    mesh.vertices[:, 1] -= mesh.vertices[:, 1].min()
    mesh.vertices[:, 2] -= mesh.vertices[:, 2].mean()
    mesh.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
        baseColorFactor=[189, 169, 205, 255], metallicFactor=0, roughnessFactor=.85))
    mesh.export(args.output / "reconstruction.glb", include_normals=True)
    if args.height_cm is not None:
        from body_geometry import render, REVISION
        recipe = {'schema': 1, 'weightsRevision': REVISION, 'shape': result['shape_params'].tolist(),
                  'modelParameters': result['mhr_model_params'].tolist(), 'declaredHeight': args.height_cm,
                  'measurements': {'height': args.height_cm}}
        recipe = render(recipe, args.output / 'reconstruction.glb')
        recipe['measurements'] = dict(recipe['estimated'])
        (args.output / 'body.json').write_text(json.dumps(recipe, allow_nan=False), encoding='utf-8')
    if not args.private:
        for filename in ("babylon.js", "babylonjs.loaders.min.js", "BABYLON-LICENSE.txt"):
            shutil.copyfile(ROOT / "static" / filename, args.output / filename)
        shutil.copyfile(Path(__file__).with_name("preview.html"), args.output / "index.html")
        shutil.copyfile(args.image, args.output / ("input" + args.image.suffix.lower()))
    report = {
        "status": "passed", "model": "facebook/sam-3d-body-vith", "inferenceType": "body",
        "sourceRevision": "b5c765a0d89d789985e186d396315e7590887b94",
        "weightsRevision": "f7f4ba4f67739e297f291639afb7c59041745367",
        "device": torch.cuda.get_device_name(), "torch": torch.__version__,
        "loadSeconds": round(loaded - started, 2), "inferenceSeconds": round(finished - loaded, 2),
        "peakAllocatedMiB": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
        "peakReservedMiB": round(torch.cuda.max_memory_reserved() / 1024**2, 1),
        "freeBeforeMiB": round(free_before / 1024**2, 1), "totalMiB": round(total / 1024**2, 1),
        "vertices": len(vertices), "triangles": len(faces), "measurementsValidated": False,
        "inputFile": "input" + args.image.suffix.lower(),
        "warning": "Reconstruction test only. No anthropometric calibration or image-quality validation.",
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
