from io import BytesIO
import time

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from sam.mobile_api import app, Jobs


def photo():
    buffer = BytesIO()
    Image.new('RGB', (300, 400)).save(buffer, format='PNG')
    return buffer.getvalue()


def test_upload_poll_model_discard_and_validation():
    with TestClient(app) as client:
        original = app.state.jobs
        app.state.jobs = Jobs(lambda data: b'glTFfake-test-mesh')
        original.close()
        assert client.post('/api/reconstructions', data={'height_cm': 170, 'weight_kg': 65},
                           files={'photo': ('body.png', b'bad', 'image/png')}).status_code == 422
        response = client.post('/api/reconstructions', data={'height_cm': 170, 'weight_kg': 65},
                               files={'photo': ('body.png', photo(), 'image/png')})
        assert response.status_code == 202
        key = response.json()['id']
        for _ in range(100):
            result = client.get(f'/api/reconstructions/{key}').json()
            if result['status'] == 'succeeded':
                break
            time.sleep(.01)
        assert result['status'] == 'succeeded'
        assert result['measurementsValidated'] is False
        assert client.get(f'/api/reconstructions/{key}/model.glb').content == b'glTFfake-test-mesh'
        assert client.get(f'/view/{key}').status_code == 200
        assert client.get('/assets/../mobile_api.py').status_code == 404
        assert client.get('/health', headers={'Origin': 'https://example.com'}).status_code == 403
        client.delete(f'/api/reconstructions/{key}')
        assert client.get(f'/api/reconstructions/{key}').status_code == 404


def test_capacity_and_expiration():
    jobs = Jobs(lambda data: b'glTFtest')
    try:
        key = jobs.submit(b'one')
        jobs.submit(b'two')
        with pytest.raises(Exception) as error:
            jobs.submit(b'three')
        assert error.value.status_code == 429
        jobs.expire(key)
        with pytest.raises(Exception) as error:
            jobs.get(key)
        assert error.value.status_code == 404
    finally:
        jobs.close()


def test_owner_bound_adjust_save_and_restore(monkeypatch):
    import sam.mobile_api as api
    from fastapi import HTTPException
    user = ['owner-a']
    stored = {}
    def identity(request):
        if request.headers.get('authorization') != 'Bearer test-session':
            raise HTTPException(401, 'sign_in_required')
        return user[0], 'Bearer test-session'
    class Store:
        def __init__(self, owner, bearer): self.owner = owner
        def get(self): return stored.get(self.owner)
        def save(self, recipe, photo, fit, photo_path=None):
            stored[self.owner] = {'body': recipe, 'photo_path': 'private/photo.jpg', 'fit_preference': fit}
            assert photo == b'clean-photo'
            return 'private/photo.jpg'
    monkeypatch.setattr(api, 'identity', identity)
    monkeypatch.setattr(api, 'AvatarStore', Store)
    recipe = {'schema': 1, 'measurements': {'height': 170, 'chest': 90}, 'shape': [0] * 45}
    def runner(payload):
        return {'model': b'glTFtest', 'body': payload.get('recipe', recipe), 'photo': b'clean-photo'}
    with TestClient(app) as client:
        app.state.jobs.close()
        app.state.jobs = Jobs(runner)
        key = app.state.jobs.submit({}, owner='owner-a')
        for _ in range(100):
            if app.state.jobs.get(key)['status'] == 'succeeded': break
            time.sleep(.01)
        route = f'/api/reconstructions/{key}/profile'
        body = {'measurements': {'height': 175, 'waist': 75, 'shoulderWidth': None}, 'fitPreference': 'Fitted'}
        assert client.put(route, json=body).status_code == 401
        headers = {'Authorization': 'Bearer test-session'}
        user[0] = 'owner-b'
        assert client.put(route, json=body, headers=headers).status_code == 403
        user[0] = 'owner-a'
        assert client.put(route, json=body, headers=headers).status_code == 200
        assert stored['owner-a']['body']['measurements']['height'] == 175
        assert 'model' not in stored['owner-a']['body']
        client.delete(f'/api/reconstructions/{key}')
        assert client.post('/api/avatar/open', headers=headers).status_code == 202
