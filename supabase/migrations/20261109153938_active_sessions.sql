begin;
-- This schema is not exposed through the Data API.
create schema mirage_private;
revoke all on schema mirage_private from public,anon;
grant usage on schema mirage_private to authenticated;

-- Only this narrowly scoped helper can read auth.sessions. It returns information
-- about the authenticated caller's own session, never arbitrary users or sessions.
create function mirage_private.session_active() returns boolean
language sql stable security definer set search_path = '' as $$
    select auth.uid() is not null and exists (
        select 1 from auth.sessions s
        where s.id = (auth.jwt()->>'session_id')::uuid
          and s.user_id = auth.uid()
          and (s.not_after is null or s.not_after > now())
    );
$$;
revoke all on function mirage_private.session_active() from public,anon;
grant execute on function mirage_private.session_active() to authenticated;

create function public.mirage_session_active() returns boolean
language sql stable security invoker set search_path = '' as $$
    select mirage_private.session_active();
$$;
revoke all on function public.mirage_session_active() from public,anon;
grant execute on function public.mirage_session_active() to authenticated;

-- Child-table policies already require a visible owned user_profiles row.
alter policy profile_owner on public.user_profiles to authenticated
using ((select auth.uid())=user_id and (select public.mirage_session_active()))
with check ((select auth.uid())=user_id and (select public.mirage_session_active()));
commit;
