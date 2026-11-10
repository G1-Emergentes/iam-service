import json
import numpy as np
import trimesh
from mesh_engine import AnnyMeshEngine, ROOT
from domain import BodyMeasurements
engine=AnnyMeshEngine()
ROOT.joinpath('output').mkdir(exist_ok=True)
first = engine.generate(BodyMeasurements(170,40,92,78,96),ROOT/'output'/'sample.glb')
second = engine.generate(BodyMeasurements(180,42,100,90,102),ROOT/'output'/'sample-tall.glb')
assert (ROOT/'output'/'sample.glb').read_bytes()[:4] == b'glTF'
mesh = trimesh.load(ROOT/'output'/'sample.glb', force='mesh')
taller = trimesh.load(ROOT/'output'/'sample-tall.glb', force='mesh')
assert len(mesh.vertices) > 1000 and np.isfinite(mesh.vertices).all()
assert abs(np.ptp(mesh.vertices[:,1]) - 1.7) < .001
assert abs(np.ptp(taller.vertices[:,1]) - 1.8) < .001
assert not np.allclose(mesh.vertices, taller.vertices)
for result in (first, second):
    assert result['approximate'] is True
    assert result['withinTolerance'] is True, result['errorCm']
    assert all(np.isfinite(list(result['achieved'].values())))
    for name in result['requested']:
        assert abs(result['achieved'][name] - result['requested'][name] - result['errorCm'][name]) < .02
print(json.dumps({'realMeshChecks':'passed','sample':first,'tallerSample':second},ensure_ascii=True))
