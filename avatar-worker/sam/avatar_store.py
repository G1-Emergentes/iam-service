"""Private photo + compact recipe; caller's bearer is checked by IAM and RLS."""
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import httpx
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
BUCKET = 'mirage-avatar-photos'


def config():
    values = dict(os.environ)
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            name, separator, value = line.partition('=')
            if separator and name in ('SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY'):
                values.setdefault(name, value.strip().strip('"'))
    try:
        return values['SUPABASE_URL'].rstrip('/'), values['SUPABASE_PUBLISHABLE_KEY']
    except KeyError:
        raise HTTPException(503, 'storage_not_configured')


def identity(request):
    bearer = request.headers.get('authorization', '')
    if not bearer.startswith('Bearer ') or len(bearer) > 8192:
        raise HTTPException(401, 'sign_in_required')
    try:
        result = httpx.get('http://127.0.0.1:8080/api/v1/auth/me', headers={'Authorization': bearer}, timeout=15)
        if result.status_code != 200:
            raise HTTPException(401, 'session_expired')
        return result.json()['id'], bearer
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(503, 'iam_unavailable')


class AvatarStore:
    def __init__(self, user, bearer):
        self.user = user
        self.url, key = config()
        self.headers = {'apikey': key, 'Authorization': bearer}

    def request(self, method, path, **kwargs):
        headers = dict(self.headers)
        headers.update(kwargs.pop('headers', {}))
        try:
            response = httpx.request(method, self.url + path, headers=headers, timeout=30, **kwargs)
            if response.status_code >= 400:
                raise HTTPException(502, 'private_storage_failed')
            return response
        except httpx.HTTPError:
            raise HTTPException(502, 'private_storage_unavailable')

    def get(self):
        rows = self.request('GET', '/rest/v1/avatar_profiles', params={'user_id': 'eq.' + self.user, 'select': '*'}).json()
        return rows[0] if rows else None

    def save(self, recipe, photo, fit, photo_path=None):
        if photo_path is None:
            photo_path = self.user + '/' + str(uuid4()) + '.jpg'
            self.request('POST', '/storage/v1/object/' + BUCKET + '/' + photo_path,
                         content=photo, headers={'Content-Type': 'image/jpeg', 'x-upsert': 'false'})
        self.request('POST', '/rest/v1/avatar_profiles', params={'on_conflict': 'user_id'},
                     headers={'Prefer': 'resolution=merge-duplicates'}, json={
                         'user_id': self.user, 'photo_path': photo_path, 'body': recipe, 'fit_preference': fit,
                         'updated_at': datetime.now(timezone.utc).isoformat()})
        return photo_path

    def photo(self, path):
        if not path.startswith(self.user + '/') or '..' in path:
            raise HTTPException(403, 'photo_access_denied')
        return self.request('GET', '/storage/v1/object/authenticated/' + BUCKET + '/' + path).content
