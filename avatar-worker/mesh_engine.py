"""Native Anny topology only: no SMPL assets, hosted APIs or photo inference."""
import os
from pathlib import Path
import time

import numpy as np
from scipy.optimize import least_squares
import torch
import trimesh

from domain import BodyMeasurements

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("ANNY_CACHE_DIR", str(ROOT / ".cache"))


def torso_section(mesh, fraction):
    """Approximate circumference at a relative standing height, in metres."""
    low, high = mesh.bounds[:, 2]
    section = mesh.section(plane_origin=[0, 0, low + fraction * (high - low)],
                           plane_normal=[0, 0, 1])
    if section is None:
        raise ValueError("Cannot measure this mesh section")
    loops = [p for p in section.discrete if len(p) > 3 and
             np.linalg.norm(p[0] - p[-1]) < 1e-5 and
             p[:, 0].min() < 0 < p[:, 0].max()]
    if not loops:
        raise ValueError("No closed torso section")
    # Arms can intersect the same plane; use the closed loop crossing the midline.
    loop = min(loops, key=lambda p: abs(p[:, 0].mean()))
    return float(np.linalg.norm(np.diff(loop, axis=0), axis=1).sum())


class AnnyMeshEngine:
    def __init__(self):
        import anny
        torch.set_num_threads(2)
        self.model = anny.Anny(rig="anny", topology="anny", local_changes="default").to(dtype=torch.float32)
        self.model.eval()
        self.faces = self.model.faces.cpu().numpy()
        self.parameters = ["measure-shoulder-dist-incr", "measure-bust-circ-incr",
                           "measure-waist-circ-incr", "measure-hips-circ-incr",
                           "torso-scale-horiz-incr", "torso-scale-depth-incr"]
        self.anthropometry = anny.Anthropometry(self.model)
        self.shoulders = anny.KeypointsRegressor.coco(self.model)
        self.base = self._vertices({})
        self.positive = np.stack([self._vertices({name: 1.0}) - self.base
                                  for name in self.parameters])
        self.negative = np.stack([self._vertices({name: -1.0}) - self.base
                                  for name in self.parameters])

    def _vertices(self, changes):
        with torch.inference_mode():
            result = self.model(phenotype_kwargs={"age": 0.67},
                                local_changes_kwargs=changes)
        return result["vertices"][0].cpu().numpy().astype(np.float64)

    def _mesh(self, changes, height):
        vertices = (self.base + np.einsum("i,ivd->vd", np.maximum(changes, 0), self.positive)
                    + np.einsum("i,ivd->vd", np.maximum(-changes, 0), self.negative))
        vertices *= height / 100 / np.ptp(vertices[:, 2])
        vertices[:, 2] -= vertices[:, 2].min()
        return trimesh.Trimesh(vertices=vertices, faces=self.faces, process=False)

    def measure(self, mesh):
        vertices = torch.as_tensor(mesh.vertices[None], dtype=torch.float32)
        with torch.inference_mode():
            points = self.shoulders({"vertices": vertices})[0].numpy()
            labels = self.shoulders.labels
            shoulder = np.linalg.norm(points[labels.index("left_shoulder")] -
                                      points[labels.index("right_shoulder")])
            waist = self.anthropometry.waist_circumference(vertices).item()
        # These sections are geometric proxies, not validated anatomical landmarks.
        return {"height": float(np.ptp(mesh.vertices[:, 2]) * 100),
                "shoulderWidth": float(shoulder * 100),
                "chest": torso_section(mesh, 0.72) * 100,
                "waist": waist * 100,
                "hip": torso_section(mesh, 0.52) * 100}

    def generate(self, measurements: BodyMeasurements, destination: Path):
        started = time.perf_counter()
        requested = measurements.to_dict()
        names = ["shoulderWidth", "chest", "waist", "hip"]

        def residual(changes):
            measured = self.measure(self._mesh(changes, measurements.height))
            return [(measured[name] - requested[name]) / 5 for name in names] + list(changes * 0.03)

        def jacobian(changes):
            # Float32 landmark regressors need a finite step even at zero parameters.
            baseline = np.asarray(residual(changes))
            columns = []
            for index in range(len(self.parameters)):
                step = 0.01 if changes[index] <= 0.99 else -0.01
                moved = changes.copy()
                moved[index] += step
                columns.append((np.asarray(residual(moved)) - baseline) / step)
            return np.stack(columns, axis=1)

        fit = least_squares(residual, np.zeros(len(self.parameters)), jac=jacobian, bounds=(-1, 1),
                            max_nfev=35, ftol=0.01, xtol=0.01)
        mesh = self._mesh(fit.x, measurements.height)
        achieved = self.measure(mesh)
        errors = {name: round(achieved[name] - requested[name], 2) for name in requested}
        # GLB uses Y-up; Anny's native mesh is Z-up.
        mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
        mesh.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
            baseColorFactor=[189, 169, 205, 255], metallicFactor=0, roughnessFactor=0.85))
        data = mesh.export(file_type="glb", include_normals=True)
        temporary = destination.with_suffix(".tmp")
        temporary.write_bytes(data)
        temporary.replace(destination)
        return {"model": "anny", "modelVersion": "0.6.2", "units": "cm",
                "requested": requested, "achieved": {k: round(v, 2) for k, v in achieved.items()},
                "errorCm": errors, "approximate": True,
                "withinTolerance": all(abs(v) <= 3 for v in errors.values()),
                "durationSeconds": round(time.perf_counter() - started, 2),
                "warning": "Avatar aproximado. Pecho y cadera usan secciones geométricas; "
                           "no son medidas anatómicas validadas ni una predicción del ajuste de ropa."}
