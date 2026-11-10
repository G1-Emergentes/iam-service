"""Explicit live tests against the existing, agent-created Mirage test account.
Changes ONLY that test account's Mirage password; never its Gmail password.
Admin credentials are retrieved into memory for recovery-code generation only.
No admin key, JWT or verification code is printed or written to disk.
"""
import argparse
import json
import re
import secrets
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--allow-password-change',action='store_true',required=True)
parser.add_argument('--project-ref',required=True)
parser.add_argument('--send-test-email',action='store_true')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
def config(path):
    return dict(line.split('=',1) for line in path.read_text(encoding='utf-8-sig').splitlines() if '=' in line and not line.startswith('#'))
settings=config(root/'.env')
fixture=config(root/'.env.auth-test')
origin=settings['SUPABASE_URL']
if origin!='https://'+args.project_ref+'.supabase.co' or not re.fullmatch('[a-z0-9]{20}',args.project_ref):
    raise SystemExit('Project ref must match the configured Supabase origin')

def request(origin,path,body=None,token=None,key=None,method=None):
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    if key: headers['apikey']=key
    req=urllib.request.Request(origin+path,headers=headers,
        data=json.dumps(body).encode() if body is not None else None,
        method=method or ('POST' if body is not None else 'GET'))
    try: response=urllib.request.urlopen(req,timeout=30)
    except urllib.error.HTTPError as e: response=e
    with response:
        data=response.read()
        return response.status,json.loads(data) if data else {}

def api(path,body=None,token=None,method=None):
    return request('http://127.0.0.1:8080','/api/v1/auth/'+path,body,token,method=method)

def check(value,message):
    if not value: raise RuntimeError(message)

def login(password):
    status,value=api('login',{'email':fixture['AUTH_TEST_EMAIL'],'password':password})
    check(status==200 and value.get('profile_ready') is True,'Live test login failed')
    return value

active_tokens=[]
try:
    first=login(fixture['AUTH_TEST_PASSWORD']);active_tokens.append(first['access_token'])
    second=login(fixture['AUTH_TEST_PASSWORD']);active_tokens.append(second['access_token'])
    check(api('logout',{},first['access_token'])[0]==200,'Logout failed')
    check(api('me',token=first['access_token'])[0]==401,'Old access token still reaches Mirage')
    check(api('me',token=second['access_token'])[0]==200,'Logout affected the other session')
    status,value=request(origin,'/rest/v1/rpc/mirage_session_active',{},first['access_token'],settings['SUPABASE_PUBLISHABLE_KEY'])
    check(status==200 and value is False,'Revoked session still passes database guard')
    status,value=request(origin,'/rest/v1/rpc/mirage_get_profile',{},first['access_token'],settings['SUPABASE_PUBLISHABLE_KEY'])
    check(status==200 and value is None,'Revoked session still reads Profile via Data API')
    check(api('refresh',{'refresh_token':first['refresh_token']})[0] in (400,401),'Revoked refresh token accepted')
    check(api('reset-password',{'password':'NeverApplied-Test-Password'},first['access_token'],'PUT')[0]==401,'Revoked session can change password')
    print('PASS: immediate logout, direct RLS denial, isolated sessions, rejected revoked refresh/password change',flush=True)

    command=['npx.cmd','--yes','supabase@3.0.0','projects','api-keys','--remote='+args.project_ref,'--reveal','--output-format','json']
    cli=subprocess.run(command,cwd=root,capture_output=True,text=True,check=False)
    check(cli.returncode==0,'Unable to obtain the test admin credential')
    keys=json.loads(cli.stdout)['keys']
    admin=next(item for item in keys if item.get('name')=='service_role')
    admin_key=admin.get('api_key') or admin.get('key')
    check(bool(admin_key),'No admin key available for recovery test')
    status,generated=request(origin,'/auth/v1/admin/generate_link',
        {'type':'recovery','email':fixture['AUTH_TEST_EMAIL']},admin_key,admin_key)
    check(status==200,'Recovery test code generation failed')
    code=generated.get('email_otp') or generated.get('properties',{}).get('email_otp')
    check(bool(code),'Provider did not return a recovery code')
    status,recovery=api('verify-email',{'email':fixture['AUTH_TEST_EMAIL'],'token':code,'type':'recovery'})
    check(status==200 and bool(recovery.get('access_token')),'Recovery code verification failed')
    active_tokens.append(recovery['access_token'])
    replay_status,replay=api('verify-email',{'email':fixture['AUTH_TEST_EMAIL'],'token':code,'type':'recovery'})
    check(replay_status in (400,401) and not replay.get('access_token'),'Recovery code replay not rejected: status '+str(replay_status))
    new_password=secrets.token_urlsafe(32)
    pending=dict(fixture,AUTH_TEST_PASSWORD=new_password)
    pending_path=root/'.env.auth-test.pending-reset'
    pending_path.write_text(''.join(k+'='+v+'\n' for k,v in pending.items()),encoding='utf-8')
    status,changed=api('reset-password',{'password':new_password},recovery['access_token'],'PUT')
    if status==200 or changed.get('error')=='password_changed_session_revocation_failed':
        (root/'.env.auth-test').write_text(pending_path.read_text(encoding='utf-8'),encoding='utf-8')
    check(status==200 and changed.get('reauthentication_required') is True,'Password reset or global revocation failed')
    check(api('me',token=second['access_token'])[0]==401,'Previous session survived password reset')
    check(api('me',token=recovery['access_token'])[0]==401,'Recovery session survived password reset')
    check(api('login',{'email':fixture['AUTH_TEST_EMAIL'],'password':fixture['AUTH_TEST_PASSWORD']})[0] in (400,401),'Old password accepted after reset')
    last=login(new_password);active_tokens.append(last['access_token'])
    check(api('logout',{},last['access_token'])[0]==200,'Final cleanup logout failed')
    print('PASS: one-use recovery code, real password reset, global session revocation, old-password rejection, new login',flush=True)

    status,known=api('resend-verification',{'email':fixture['AUTH_TEST_EMAIL']})
    status_unknown,unknown=api('resend-verification',{'email':'no-such-mirage-user@example.invalid'})
    check(status==status_unknown==200 and known==unknown,'Resend reveals account existence')
    print('PASS: resend gives the same generic response for confirmed and unknown accounts',flush=True)
    if args.send_test_email:
        status,_=api('forgot-password',{'email':fixture['AUTH_TEST_EMAIL']})
        check(status==200,'Recovery email was not accepted by provider')
        print('PASS: provider accepted a real recovery email to the configured test inbox',flush=True)
finally:
    for token in active_tokens:
        try: api('logout',{},token)
        except Exception: pass
