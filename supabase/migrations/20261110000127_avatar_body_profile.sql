create table public.avatar_profiles (
 user_id uuid primary key references auth.users(id) on delete cascade,
 photo_path text not null check (photo_path like user_id::text || '/%'),
 body jsonb not null check (jsonb_typeof(body)='object' and body->>'schema'='1'
   and jsonb_array_length(body->'shape')=45 and jsonb_array_length(body->'modelParameters')=204),
 fit_preference text not null check (fit_preference in ('Fitted','Regular','Oversized')),
 updated_at timestamptz not null default now()
);
alter table public.avatar_profiles enable row level security;
create policy avatar_profile_owner on public.avatar_profiles for all to authenticated
using ((select auth.uid())=user_id and (select public.mirage_session_active()))
with check ((select auth.uid())=user_id and (select public.mirage_session_active()));
revoke all on public.avatar_profiles from anon,authenticated;
grant select,insert,update on public.avatar_profiles to authenticated;
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values ('mirage-avatar-photos','mirage-avatar-photos',false,8388608,array['image/jpeg']);
create policy avatar_photo_read on storage.objects for select to authenticated
using (bucket_id='mirage-avatar-photos' and (storage.foldername(name))[1]=(select auth.uid())::text and (select public.mirage_session_active()));
create policy avatar_photo_insert on storage.objects for insert to authenticated
with check (bucket_id='mirage-avatar-photos' and (storage.foldername(name))[1]=(select auth.uid())::text and (select public.mirage_session_active()));
create policy avatar_photo_delete on storage.objects for delete to authenticated
using (bucket_id='mirage-avatar-photos' and (storage.foldername(name))[1]=(select auth.uid())::text and (select public.mirage_session_active()));
