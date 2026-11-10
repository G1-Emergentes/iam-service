"""Tests the migration in a NEW database on the isolated local cluster, never Supabase.
Requires psycopg2 and PostgreSQL running on 127.0.0.1:55439.
"""
from pathlib import Path
import uuid
import json
import psycopg2
from psycopg2 import sql

root=Path(__file__).resolve().parents[1]
admin=psycopg2.connect(host='127.0.0.1',port=55439,user='postgres',dbname='postgres')
admin.autocommit=True
name='profile_test_'+uuid.uuid4().hex
with admin.cursor() as c:
    c.execute(sql.SQL('create database {}').format(sql.Identifier(name)))
admin.close()
con=psycopg2.connect(host='127.0.0.1',port=55439,user='postgres',dbname=name)
con.autocommit=True
c=con.cursor()
for role in ['anon','authenticated']:
    c.execute('select 1 from pg_roles where rolname=%s',(role,))
    if not c.fetchone(): c.execute(sql.SQL('create role {}').format(sql.Identifier(role)))
c.execute("""
create schema auth;
create table auth.users (id uuid primary key);
create table auth.sessions (id uuid primary key,user_id uuid,not_after timestamptz);
create function auth.jwt() returns jsonb language sql stable as $$
    select coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb;
$$;
create function auth.uid() returns uuid language sql stable as $$
    select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid;
$$;
grant usage on schema auth,public to authenticated;
grant execute on function auth.uid() to authenticated;
""")
a='22222222-2222-2222-2222-222222222222'
b='33333333-3333-3333-3333-333333333333'
c.execute('insert into auth.users values (%s),(%s)',(a,b))
sa='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
sb='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
c.execute('insert into auth.sessions(id,user_id) values(%s,%s),(%s,%s)',(sa,a,sb,b))
for migration in sorted((root/'supabase/migrations').glob('*.sql')):
    c.execute(migration.read_text())
c.execute('set role authenticated')
def actor(user):
    c.execute("select set_config('request.jwt.claim.sub',%s,false)",(user,))
    c.execute("select set_config('request.jwt.claims',%s,false)",(json.dumps({'sub':user,'session_id':sa if user==a else sb,'role':'authenticated'}),))
def rpc(name,payload=None):
    if payload is None: c.execute(sql.SQL('select public.{}()').format(sql.Identifier(name)))
    else: c.execute(sql.SQL('select public.{}(%s::jsonb)').format(sql.Identifier(name)),(json.dumps(payload),))
    return c.fetchone()[0]
actor(a)
assert rpc('mirage_get_profile') is None
profile=rpc('mirage_create_profile',{'id':str(uuid.uuid4()),'displayName':'Mateo','birthDate':'2000-02-29'})
assert profile['userId']==a and profile['measurements'] is None
prefs={'preferredStyles':['casual'],'preferredColors':['blue'],'avoidedColors':[],'preferredCategories':['shirt']}
assert rpc('mirage_set_preferences',prefs)['preferences']==prefs
measurements={'height':175,'shoulderWidth':45,'chest':95,'waist':80,'hip':96}
assert rpc('mirage_set_measurements',measurements)['measurements']==measurements
try:
    rpc('mirage_set_preferences',dict(prefs,preferredStyles=['casual','casual']))
    raise AssertionError('Duplicate preference accepted')
except psycopg2.errors.UniqueViolation: pass
assert rpc('mirage_get_profile')['preferences']==prefs, 'Preference replacement was not atomic'
try:
    rpc('mirage_set_measurements',dict(measurements,height=-1))
    raise AssertionError('Negative measurement accepted')
except psycopg2.errors.CheckViolation: pass
assert rpc('mirage_get_profile')['measurements']['height']==175
actor(b)
assert rpc('mirage_get_profile') is None
for table in ['user_profiles','body_measurements','style_preferences']:
    c.execute(sql.SQL('select count(*) from public.{}').format(sql.Identifier(table)))
    assert c.fetchone()[0]==0, 'RLS leaked another user data'
try:
    c.execute('insert into public.body_measurements values (%s,175,45,95,80,96)',(profile['id'],))
    raise AssertionError('Foreign measurements accepted')
except (psycopg2.errors.InsufficientPrivilege,psycopg2.errors.UniqueViolation): pass
actor(a)
assert rpc('mirage_update_profile',{'displayName':'Mateo updated','birthDate':None})['displayName']=='Mateo updated'
assert rpc('mirage_get_profile')['measurements']==measurements
c.execute('reset role')
c.execute('delete from auth.sessions where id=%s',(sa,))
c.execute('set role authenticated')
actor(a)
assert rpc('mirage_session_active') is False
assert rpc('mirage_get_profile') is None
for table in ['user_profiles','style_preferences','body_measurements']:
    c.execute(sql.SQL('select count(*) from public.{}').format(sql.Identifier(table)))
    assert c.fetchone()[0]==0, 'Revoked session still accesses personal data'
c.execute('reset role')
c.execute('set role anon')
try:
    rpc('mirage_get_profile')
    raise AssertionError('Anonymous RPC accepted')
except psycopg2.errors.InsufficientPrivilege: pass
c.close();con.close()
print('PASS: PostgreSQL migration, persisted aggregate, atomic preferences, validation, RLS ownership, immediate session revocation, anonymous denial')
