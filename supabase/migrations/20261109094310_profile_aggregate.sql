-- Additive schema: aborts on conflicting object names, never drops existing data.
begin;
create table public.user_profiles (
    id uuid primary key,
    user_id uuid not null unique references auth.users(id),
    display_name text not null check (length(btrim(display_name)) between 1 and 100),
    birth_date date check (birth_date >= date '1900-01-01' and birth_date <= current_date),
    profile_image_url text check (profile_image_url is null or (length(profile_image_url) between 9 and 2048 and profile_image_url like 'https://%')),
    avatar_reference text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create table public.style_preferences (
    profile_id uuid not null references public.user_profiles(id),
    kind text not null check (kind in ('STYLE','COLOR','AVOIDED_COLOR','CATEGORY')),
    value text not null check (length(btrim(value)) between 1 and 80),
    primary key (profile_id,kind,value)
);
create table public.body_measurements (
    profile_id uuid primary key references public.user_profiles(id),
    height numeric not null check (height > 0 and height <= 1000),
    shoulder_width numeric not null check (shoulder_width > 0 and shoulder_width <= 1000),
    chest numeric not null check (chest > 0 and chest <= 1000),
    waist numeric not null check (waist > 0 and waist <= 1000),
    hip numeric not null check (hip > 0 and hip <= 1000)
);
comment on table public.body_measurements is 'BodyMeasurements value object; all values are centimetres.';
alter table public.user_profiles enable row level security;
alter table public.style_preferences enable row level security;
alter table public.body_measurements enable row level security;
create policy profile_owner on public.user_profiles for all to authenticated
    using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy preference_owner on public.style_preferences for all to authenticated
    using (exists(select 1 from public.user_profiles p where p.id=profile_id and p.user_id=(select auth.uid())))
    with check (exists(select 1 from public.user_profiles p where p.id=profile_id and p.user_id=(select auth.uid())));
create policy measurement_owner on public.body_measurements for all to authenticated
    using (exists(select 1 from public.user_profiles p where p.id=profile_id and p.user_id=(select auth.uid())))
    with check (exists(select 1 from public.user_profiles p where p.id=profile_id and p.user_id=(select auth.uid())));
revoke all on public.user_profiles,public.style_preferences,public.body_measurements from anon,authenticated;
grant select,insert,update on public.user_profiles,public.body_measurements to authenticated;
grant select,insert,delete on public.style_preferences to authenticated;

create function public.mirage_get_profile() returns jsonb
language sql stable security invoker set search_path = '' as $$
    select jsonb_build_object(
        'id',p.id,'userId',p.user_id,'displayName',p.display_name,'birthDate',p.birth_date,
        'profileImageUrl',p.profile_image_url,'avatarReference',p.avatar_reference,
        'createdAt',p.created_at,'updatedAt',p.updated_at,
        'preferences',jsonb_build_object(
            'preferredStyles',coalesce((select jsonb_agg(value order by value) from public.style_preferences where profile_id=p.id and kind='STYLE'),'[]'::jsonb),
            'preferredColors',coalesce((select jsonb_agg(value order by value) from public.style_preferences where profile_id=p.id and kind='COLOR'),'[]'::jsonb),
            'avoidedColors',coalesce((select jsonb_agg(value order by value) from public.style_preferences where profile_id=p.id and kind='AVOIDED_COLOR'),'[]'::jsonb),
            'preferredCategories',coalesce((select jsonb_agg(value order by value) from public.style_preferences where profile_id=p.id and kind='CATEGORY'),'[]'::jsonb)),
        'measurements',(select jsonb_build_object('height',m.height,'shoulderWidth',m.shoulder_width,
            'chest',m.chest,'waist',m.waist,'hip',m.hip) from public.body_measurements m where m.profile_id=p.id)
    ) from public.user_profiles p where p.user_id=(select auth.uid());
$$;

create function public.mirage_create_profile(p_profile jsonb) returns jsonb
language plpgsql security invoker set search_path = '' as $$
begin
    if auth.uid() is null then raise insufficient_privilege; end if;
    insert into public.user_profiles(id,user_id,display_name,birth_date,profile_image_url)
    values ((p_profile->>'id')::uuid,auth.uid(),p_profile->>'displayName',
        (p_profile->>'birthDate')::date,p_profile->>'profileImageUrl');
    return public.mirage_get_profile();
end;
$$;

create function public.mirage_update_profile(p_profile jsonb) returns jsonb
language plpgsql security invoker set search_path = '' as $$
begin
    if auth.uid() is null then raise insufficient_privilege; end if;
    update public.user_profiles set display_name=p_profile->>'displayName',
        birth_date=(p_profile->>'birthDate')::date,profile_image_url=p_profile->>'profileImageUrl',updated_at=now()
    where user_id=auth.uid();
    if not found then raise no_data_found; end if;
    return public.mirage_get_profile();
end;
$$;

create function public.mirage_set_preferences(p_preferences jsonb) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare
    profile uuid;
    list jsonb;
    item jsonb;
    field text;
    category text;
begin
    if auth.uid() is null then raise insufficient_privilege; end if;
    -- Lock the aggregate root so two preference replacements cannot interleave.
    select id into profile from public.user_profiles where user_id=auth.uid() for update;
    if not found then raise no_data_found; end if;
    if jsonb_typeof(p_preferences) is distinct from 'object' then raise check_violation; end if;
    delete from public.style_preferences where profile_id=profile;
    for field,category in select * from (values
        ('preferredStyles','STYLE'),('preferredColors','COLOR'),
        ('avoidedColors','AVOIDED_COLOR'),('preferredCategories','CATEGORY')) as categories(field,category)
    loop
        list := p_preferences->field;
        if jsonb_typeof(list) is distinct from 'array' then raise check_violation; end if;
        if jsonb_array_length(list)>50 then raise check_violation; end if;
        for item in select * from jsonb_array_elements(list) loop
            if jsonb_typeof(item) is distinct from 'string' then raise check_violation; end if;
            insert into public.style_preferences(profile_id,kind,value) values(profile,category,item #>> '{}');
        end loop;
    end loop;
    if exists(select 1 from public.style_preferences a join public.style_preferences b
        on a.profile_id=b.profile_id and a.value=b.value
        where a.profile_id=profile and a.kind='COLOR' and b.kind='AVOIDED_COLOR') then
        raise check_violation;
    end if;
    update public.user_profiles set updated_at=now() where id=profile;
    return public.mirage_get_profile();
end;
$$;

create function public.mirage_set_measurements(p_measurements jsonb) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare profile uuid;
begin
    if auth.uid() is null then raise insufficient_privilege; end if;
    select id into profile from public.user_profiles where user_id=auth.uid() for update;
    if not found then raise no_data_found; end if;
    insert into public.body_measurements(profile_id,height,shoulder_width,chest,waist,hip)
    values(profile,(p_measurements->>'height')::numeric,(p_measurements->>'shoulderWidth')::numeric,
        (p_measurements->>'chest')::numeric,(p_measurements->>'waist')::numeric,(p_measurements->>'hip')::numeric)
    on conflict(profile_id) do update set height=excluded.height,shoulder_width=excluded.shoulder_width,
        chest=excluded.chest,waist=excluded.waist,hip=excluded.hip;
    update public.user_profiles set updated_at=now() where id=profile;
    return public.mirage_get_profile();
end;
$$;
revoke all on function public.mirage_get_profile(), public.mirage_create_profile(jsonb),
    public.mirage_update_profile(jsonb), public.mirage_set_preferences(jsonb),
    public.mirage_set_measurements(jsonb) from public,anon;
grant execute on function public.mirage_get_profile(), public.mirage_create_profile(jsonb),
    public.mirage_update_profile(jsonb), public.mirage_set_preferences(jsonb),
    public.mirage_set_measurements(jsonb) to authenticated;
commit;
