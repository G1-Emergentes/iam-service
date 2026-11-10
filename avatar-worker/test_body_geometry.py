import numpy as np
import pytest
import trimesh
from sam.body_geometry import measure, adjust, validate_measurements


def test_cylinder_contours_scaling_and_optional_values():
    profile = np.vstack([[0, 0], np.c_[np.full(101, .15), np.linspace(0, 1.7, 101)], [0, 1.7]])
    mesh = trimesh.creation.revolve(profile, sections=128)
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    mesh.vertices[:, 1] -= mesh.vertices[:, 1].min()
    baseline = measure(mesh)
    assert abs(baseline['chest'] - 2 * np.pi * 15) < .2
    edited = adjust(mesh, baseline, {'height': 180, 'chest': 105, 'waist': 80, 'hip': 100})
    values = measure(edited)
    assert values['height'] == 180
    assert abs(values['chest'] - 105) < .3
    assert abs(values['waist'] - 80) < .3
    assert abs(values['hip'] - 100) < .3
    validate_measurements({'height': 170, 'shoulderWidth': None})
    with pytest.raises(ValueError): validate_measurements({'height': float('nan')})
    with pytest.raises(ValueError): validate_measurements({'height': 170, 'waist': -1})
