"""Local contract tests with a fake Supabase Auth server; creates no real users."""
import http.server
import json
import os
import socket
from pathlib import Path
import subprocess
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / 'out/build/x64-debug-vcpkg/iam-service.exe'
calls = []
profile_state = None
session_active = True
verified_codes = set()
USER_ID = "22222222-2222-2222-2222-222222222222"


class Provider(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def handle_request(self):
        global profile_state, session_active
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'null')
        calls.append((self.command, self.path, body, self.headers))
        assert self.headers['apikey'] == 'test-key'
        status, response = 200, {'id': USER_ID}
        was_active=session_active
        if self.path.startswith('/auth/v1/token?'):
            status = 400 if body.get('password') == 'incorrect' else 200
            response = {'access_token': 'access', 'refresh_token': 'refresh', 'token_type': 'bearer', 'user': {'id': USER_ID, 'user_metadata': {'display_name':'Ana'}}}
            if status == 400: response = {'error_code':'invalid_credentials'}
            if status == 200: session_active = True
            if 'grant_type=refresh_token' in self.path and not was_active:
                status,response=400,{'error_code':'refresh_token_not_found'}
                session_active=False
        elif self.path == '/auth/v1/verify':
            valid={'signup':'12345678','recovery':'87654321'}
            code=body.get('token')
            if code != valid.get(body.get('type')) or code in verified_codes:
                status,response=403,{'error_code':'otp_expired'}
            else:
                verified_codes.add(code); session_active=True
                response={'access_token':'access','refresh_token':'refresh','token_type':'bearer','user':{'id':USER_ID,'user_metadata':{'display_name':'Ana'}}}
        elif self.path == '/auth/v1/signup':
            response = {'id': 'test-user', 'email': body['email']}
        elif self.path.startswith('/auth/v1/logout?'):
            status, response = 204, None
            session_active=False
        if self.path.startswith('/rest/v1/rpc/'):
            name = self.path.rsplit('/', 1)[1]
            if name == 'mirage_session_active':
                response=session_active
                if self.headers.get('Authorization')=='Bearer db-down':
                    status,response=503,{'error':'unavailable'}
            elif name == 'mirage_create_profile':
                if profile_state:
                    status, response = 409, {'code': '23505'}
                else:
                    profile_state = dict(body['p_profile'], createdAt='2026-11-09T00:00:00Z', updatedAt='2026-11-09T00:00:00Z')
                    response = profile_state
            elif name == 'mirage_update_profile':
                for field in ['displayName', 'birthDate', 'profileImageUrl']:
                    profile_state[field] = body['p_profile'][field]
                response = profile_state
            elif name == 'mirage_set_preferences':
                profile_state['preferences'] = body['p_preferences']
                response = profile_state
            elif name == 'mirage_set_measurements':
                profile_state['measurements'] = body['p_measurements']
                response = profile_state
            else:
                response = profile_state
        if self.headers.get('Authorization') == 'Bearer invalid':
            status, response = 401, {'message': 'private provider diagnostic'}
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        if status != 204:
            self.wfile.write(json.dumps(response).encode())

    do_GET = do_POST = do_PUT = handle_request


def request(path, body=None, method='POST', token=None, raw=None, check_no_store=True):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = raw if raw is not None else json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request('http://127.0.0.1:8080' + path, data=data, headers=headers, method=method)
    try:
        response = urllib.request.urlopen(req, timeout=15)
    except urllib.error.HTTPError as err:
        response = err
    with response:
        payload = response.read().decode()
        if path != '/health' and check_no_store:
            assert response.headers.get('Cache-Control') == 'no-store'
        if path == '/health':
            assert response.headers.get_content_type() == 'text/plain'
        return response.status, payload


def start(env):
    try:
        connection = socket.create_connection(('127.0.0.1', 8080), timeout=.3)
    except OSError:
        pass
    else:
        connection.close()
        raise RuntimeError('Stop the server on port 8080 before running mock tests')
    proc = subprocess.Popen([str(EXE)], cwd=EXE.parent, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        if proc.poll() is not None:
            raise RuntimeError('Server failed to start; check whether port 8080 is occupied')
        try:
            if request('/health', method='GET') == (200, 'ok'):
                return proc
        except OSError:
            pass
        time.sleep(.1)
    proc.terminate()
    raise RuntimeError('Server not ready')


server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Provider)
threading.Thread(target=server.serve_forever, daemon=True).start()
env = dict(os.environ, SUPABASE_URL=f'http://127.0.0.1:{server.server_port}',
           SUPABASE_PUBLISHABLE_KEY='test-key')
proc = start(env)
try:
    assert request('/docs', method='GET')[0] == 200
    for page in ['/auth/recovery','/auth/verify','/auth/callback','/auth/email-flow.js','/auth/email-flow.css']:
        assert request(page,method='GET')[0]==200
    assert request('/.env', method='GET', check_no_store=False)[0] == 404
    assert request('/docs/VENDOR.md', method='GET', check_no_store=False)[0] == 404
    assert request('/docs/index.html', method='GET', check_no_store=False)[0] == 404
    status, contract = request('/openapi.json', method='GET')
    assert status == 200 and sum(len(operations) for operations in json.loads(contract)['paths'].values()) == 18
    for asset in ['swagger-ui.css','swagger-ui-bundle.js','swagger-initializer.js']:
        assert request('/docs/'+asset,method='GET')[0] == 200
    path = '/api/v1/profiles/' + USER_ID
    assert request(path, method='GET')[0] == 401
    assert request('/api/v1/profiles/33333333-3333-3333-3333-333333333333', method='GET', token='access')[0] == 403
    assert request(path, method='GET', token='access')[0] == 404
    status, body = request('/api/v1/profiles', {'displayName': 'Ana', 'birthDate': '2000-02-29'}, token='access')
    assert status == 201, body
    assert json.loads(body)['userId'] == USER_ID
    assert request('/api/v1/profiles', {'displayName': 'Duplicate'}, token='access')[0] == 409
    assert request(path, {'displayName':'Ana updated','birthDate':'2001-02-29'}, method='PUT', token='access')[0] == 400
    assert request(path, {'displayName':'Ana updated'}, method='PUT', token='access')[0] == 200
    preferences = {'preferredStyles':['casual'],'preferredColors':['blue'],'avoidedColors':[],'preferredCategories':[]}
    assert request(path+'/preferences', preferences, method='PUT', token='access')[0] == 200
    assert json.loads(request(path+'/preferences', method='GET', token='access')[1]) == preferences
    measurements = {'height':175,'shoulderWidth':45,'chest':95,'waist':80,'hip':96}
    assert request(path+'/measurements', dict(measurements,height=-1), method='PUT', token='access')[0] == 400
    assert request(path+'/measurements', dict(measurements,height='175'), method='PUT', token='access')[0] == 400
    assert request(path+'/measurements', measurements, method='PUT', token='access')[0] == 200
    assert json.loads(request(path+'/measurements', method='GET', token='access')[1]) == measurements
    result=json.loads(request(path,method='GET',token='access')[1])
    assert result['preferences']==preferences and result['measurements']==measurements
    prefix = '/api/v1/auth/'
    assert request(prefix + 'register', raw=b'{')[0] == 400
    assert request(prefix + 'register', {'email': 'bad', 'password': '123', 'name': 'A'})[0] == 400
    assert request(prefix + 'register', {'email': 'user@example.com', 'password': 'safe-password', 'name': 'Ana', 'role': 'admin'})[0] == 200
    assert calls[-1][2] == {'email': 'user@example.com', 'password': 'safe-password', 'data': {'display_name': 'Ana'}}
    assert request(prefix + 'login', {'email': 'user@example.com', 'password': 'safe-password'})[0] == 200
    assert any(call[1] == '/auth/v1/token?grant_type=password' for call in calls)
    status, body = request(prefix + 'login', {'email': 'user@example.com', 'password': 'incorrect'})
    assert status == 400 and 'access_token' not in body
    profile_state = None
    status, google = request(prefix + 'google', {'id_token': 'google-token', 'nonce': 'nonce'})
    assert status == 200 and json.loads(google)['profile_ready'] is True
    assert profile_state['userId'] == USER_ID
    assert any(call[1] == '/auth/v1/token?grant_type=id_token' for call in calls)
    assert request(prefix + 'refresh', {'refresh_token': 'refresh'})[0] == 200
    assert calls[-1][1] == '/auth/v1/token?grant_type=refresh_token'
    assert request(prefix + 'me', method='GET')[0] == 401
    assert request(prefix + 'me', method='GET', token='access')[0] == 200
    status, body = request(prefix + 'me', method='GET', token='invalid')
    assert status == 401 and 'private' not in body
    assert request(prefix + 'forgot-password', {'email': 'unknown@example.com'})[0] == 200
    assert request(prefix+'resend-verification',{'email':'user@example.com'})[0]==200
    assert calls[-1][1]=='/auth/v1/resend' and calls[-1][2]['type']=='signup'
    assert request(prefix+'verify-email',{'email':'user@example.com','token':'letters1','type':'signup'})[0]==400
    verify={'email':'user@example.com','token':'12345678','type':'signup'}
    assert request(prefix+'verify-email',verify)[0]==200
    assert request(prefix+'verify-email',verify)[0]==401
    assert request(prefix+'verify-email',dict(verify,token='87654321',type='recovery'))[0]==200
    assert request(prefix+'me',method='GET',token='db-down')[0]==503
    assert request(prefix + 'logout', token='access')[0] == 200
    assert calls[-1][1] == '/auth/v1/logout?scope=local'
    assert request(prefix+'me',method='GET',token='access')[0]==401
    assert request(path,method='GET',token='access')[0]==401
    assert request(prefix+'refresh',{'refresh_token':'refresh'})[0]==400
    assert request(prefix+'reset-password',{'password':'new-password'},method='PUT',token='access')[0]==401
    assert request(prefix+'login',{'email':'user@example.com','password':'safe-password'})[0]==200
    status,changed=request(prefix+'reset-password',{'password':'new-password'},method='PUT',token='access')
    assert status==200 and json.loads(changed)['reauthentication_required'] is True
    assert calls[-1][1]=='/auth/v1/logout?scope=global'
    assert request(prefix+'me',method='GET',token='access')[0]==401
    for _ in range(1):
        assert request(prefix + 'login', {'email': 'user@example.com', 'password': 'incorrect'})[0] == 400
    assert request(prefix + 'login', {'email': 'user@example.com', 'password': 'incorrect'})[0] == 429
    assert request(prefix + 'register', raw=b' ' * 16385)[0] == 413
finally:
    proc.terminate()
    proc.wait(timeout=5)
    server.shutdown()
    server.server_close()

env.pop('SUPABASE_URL')
proc = start(env)
try:
    assert request('/api/v1/auth/me', method='GET', token='access')[0] == 503
finally:
    proc.terminate()
    proc.wait(timeout=5)
print('PASS: auth regression, profile HTTP commands/queries, ownership, JSON mapping, validation, missing config')
