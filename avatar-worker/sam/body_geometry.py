"""Versioned MHR recipe and editable geometric proxies, not anatomical ground truth."""
import argparse
import json
from pathlib import Path
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f7f4ba4f67739e297f291639afb7c59041745367'
LEVELS = {'hip': .52, 'waist': .60, 'chest': .72}
LIMITS = {'height': (130, 220), 'chest': (40, 200), 'waist': (35, 200),
          'hip': (40, 220), 'shoulderWidth': (20, 80)}


def validate_measurements(values):
    if set(values) - set(LIMITS):
        raise ValueError('unknown_measurement')
    for name, value in values.items():
        if value is not None and (isinstance(value, bool) or not isinstance(value, (float, int)) or
                                  not np.isfinite(value) or not LIMITS[name][0] <= value <= LIMITS[name][1]):
            raise ValueError('measurement_out_of_range')
    if values.get('height') is None:
        raise ValueError('height_required')


def measure(mesh):
    low, high = mesh.bounds[:, 1]
    values = {'height': round(float(high - low) * 100, 1), 'shoulderWidth': None}
    for name, fraction in LEVELS.items():
        section = mesh.section(plane_origin=[0, low + fraction * (high - low), 0], plane_normal=[0, 1, 0])
        loops = [] if section is None else [p for p in section.discrete if len(p) > 3 and
            np.linalg.norm(p[0] - p[-1]) < 1e-5 and p[:, 0].min() < 0 < p[:, 0].max()]
        if not loops:
            values[name] = None
            continue
        loop = min(loops, key=lambda p: abs(p[:, 0].mean()))
        value = float(np.linalg.norm(np.diff(loop, axis=0), axis=1).sum()) * 100
        values[name] = round(value, 1) if LIMITS[name][0] <= value <= LIMITS[name][1] else None
    return values


def adjust(mesh, baseline, target):
    validate_measurements(target)
    mesh = mesh.copy()
    fraction = mesh.vertices[:, 1] / mesh.extents[1]
    knots = [0, .42, .52, .60, .72, .82, 1]
    ratios = [1, 1] + [target.get(name) / baseline[name] if target.get(name) and baseline.get(name) else 1
                       for name in ('hip', 'waist', 'chest')] + [1, 1]
    radius = np.interp(fraction, knots, ratios)
    mesh.vertices[:, 0] *= radius
    mesh.vertices[:, 2] *= radius
    # shortcut: shoulder editing is a smooth visual width adjustment, not a skeletal refit.
    if target.get('shoulderWidth'):
        band = mesh.vertices[(fraction > .78) & (fraction < .84)]
        current = np.ptp(band[:, 0]) * 100 if len(band) else 0
        if current:
            influence = np.interp(fraction, [0, .72, .82, .90, 1], [0, 0, 1, 0, 0])
            mesh.vertices[:, 0] *= 1 + influence * (target['shoulderWidth'] / current - 1)
    mesh.vertices[:, 1] *= target['height'] / baseline['height']
    return mesh


def render(recipe, destination):
    import torch
    if recipe.get('schema') != 1 or recipe.get('weightsRevision') != REVISION:
        raise ValueError('unsupported_body_recipe')
    validate_measurements({'height': recipe.get('declaredHeight')})
    shape = np.asarray(recipe['shape'], dtype=np.float32)
    parameters = np.asarray(recipe['modelParameters'], dtype=np.float32)
    if shape.shape != (45,) or parameters.shape != (204,) or not np.isfinite(shape).all() or not np.isfinite(parameters).all() or max(abs(shape).max(), abs(parameters).max()) > 1000:
        raise ValueError('invalid_body_recipe')
    parameters[:136] = 0  # Canonical rest pose; preserve the 68 identity scales.
    rig = torch.jit.load(str(ROOT / 'models/sam-3d-body-vith/assets/mhr_model.pt'), map_location='cpu')
    torch.set_num_threads(4)
    with torch.inference_mode():
        vertices, _ = rig(torch.from_numpy(shape)[None], torch.from_numpy(parameters)[None], torch.zeros(1, 72))
    vertices = vertices.numpy()[0] / 100
    vertices[:, 1] -= vertices[:, 1].min()
    mesh = trimesh.Trimesh(vertices=vertices, faces=rig.character_torch.mesh.faces.numpy(), process=False)
    validate_measurements(recipe['measurements'])
    mesh.vertices *= recipe['declaredHeight'] / (mesh.extents[1] * 100)
    baseline = measure(mesh)
    mesh = adjust(mesh, baseline, recipe['measurements'])
    mesh.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
        baseColorFactor=[189, 169, 205, 255], metallicFactor=0, roughnessFactor=.85))
    mesh.export(destination, include_normals=True)
    recipe['estimated'] = baseline
    recipe['method'] = 'mhr-rest-height-scaled-geometric-proxies-v1'
    recipe['measurementsValidated'] = False
    return recipe


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recipe', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    recipe = json.loads(args.recipe.read_text(encoding='utf-8'))
    render(recipe, args.output)
