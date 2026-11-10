# User & Auth Service: Profile bounded contextSeguridad de sesiones actualizada: active_sessions exige una sesión activatambién en RLS. Ver RECOVERY.md para logout inmediato y recuperación.

## Alcance del PDF

Las páginas 106-110 del informe definen el bounded context Profile dentro de la
Auth Database. El despliegue combina identidad y perfil, pero sus módulos tienen
responsabilidades distintas. La interpretación anterior que dejaba todo Profile
fuera de este servicio era demasiado limitada.

El agregado es UserProfileAggregate. Contiene:

- UserProfile: entidad con identidad propia, userId, nombre, fecha de nacimiento,
  imagen, referencia del avatar y marcas de tiempo.
- StylePreferences: value object con estilos, colores preferidos, colores evitados
  y categorías. Se reemplaza por valor; no tiene identidad independiente.
- BodyMeasurements: value object opcional con height, shoulderWidth, chest, waist
  y hip. Todas las medidas usan centímetros. No se deducen medidas ni diagnósticos.

El UUID de auth.users identifica la cuenta, propiedad de Supabase Auth. No se
duplican sus contraseñas ni sus tokens en una entidad de dominio local.
El perfil se crea explícitamente mediante POST /api/v1/profiles durante onboarding;
la creación automática al registrar una cuenta Google todavía no está implementada.

## Organización

```text
AuthController.h/.cpp              HTTP de Auth; mantiene sus rutas existentes
auth/
  application/
    AccountService.h/.cpp         Coordina sesiones y provisión idempotente del perfil
    AuthCommands.h                Comandos tipados y consulta del usuario actual
    AuthCommandService.h/.cpp      Coordinación de escrituras; AuthQueryService para lectura
    IdentityProvider.h            Puerto del proveedor de identidad
  infrastructure/
    SupabaseIdentityProvider.*    Traducción a la API de Supabase Auth
profile/
  domain/
    model/
      UserProfileAggregate.*      Reglas y cambios del agregado
      UserProfile.h               Entidad
      StylePreferences.h          Value object
      BodyMeasurements.h          Value object
    repositories/
      ProfileRepository.h         Puerto de persistencia y resultado tipado
  application/
    ProfileCommands.h             Comandos y consulta tipados
    ProfileServices.h/.cpp        ProfileCommandService y ProfileQueryService
    PreferencesService.h/.cpp     Comandos y consultas de preferencias
  infrastructure/
    SupabaseProfileRepository.*   Persistencia mediante RPC con el JWT del usuario
    ProfileJsonMapper.*           JSON de entrada/salida; fuera del dominio
  interfaces/
    ProfileController.*           Validación HTTP, identidad y rutas
shared/
  application/ApiResult.h
  infrastructure/SupabaseClient.* Transporte HTTPS asíncrono
  interfaces/HttpSupport.*        Respuestas, validación HTTP y límite de intentos
```

CQRS separa comandos que cambian estado de consultas que solo leen. Ambos usan
la misma base de datos. No se requieren bases separadas, un bus o event sourcing
para esta separación. El dominio compila sin Drogon ni JsonCpp.

Flujo de escritura: Controller -> comando -> CommandService -> agregado ->
ProfileRepository -> Supabase. Flujo de lectura: Controller -> GetProfileQuery ->
QueryService -> repositorio -> resultado. La autenticación se verifica antes de
ejecutar cada operación. El userId de la ruta debe coincidir con la cuenta verificada.

## Rutas de Profile

Todas requieren Authorization: Bearer ACCESS_TOKEN. Las rutas que incluyen userId
solo admiten el UUID del usuario autenticado; no son consultas públicas.

| Método y ruta | Operación |
| --- | --- |
| POST /api/v1/profiles | Crear perfil; 201 o 409 si ya existe |
| GET /api/v1/profiles/{userId} | Leer el agregado completo |
| PUT /api/v1/profiles/{userId} | Reemplazar nombre, fecha de nacimiento e imagen |
| GET /api/v1/profiles/{userId}/preferences | Leer preferencias |
| PUT /api/v1/profiles/{userId}/preferences | Reemplazar las cuatro listas de preferencias |
| GET /api/v1/profiles/{userId}/measurements | Leer medidas; null si aún no se registraron |
| PUT /api/v1/profiles/{userId}/measurements | Registrar/reemplazar las cinco medidas |

Crear/actualizar perfil:

```json
{"displayName":"Mateo","birthDate":"2000-02-29","profileImageUrl":null}
```

En PUT, omitir birthDate o profileImageUrl los deja en null; no es PATCH.
id, userId, avatarReference y timestamps no se toman del cuerpo HTTP para escritura.
Los demás datos del agregado se conservan al actualizar un componente.

Preferencias:

```json
{"preferredStyles":["casual"],"preferredColors":["blue"],"avoidedColors":[],"preferredCategories":["shirt"]}
```

Medidas (cm):

```json
{"height":175,"shoulderWidth":45,"chest":95,"waist":80,"hip":96}
```

Reglas de implementación: medidas numéricas finitas mayores que cero y hasta
1000 cm (límite técnico, no criterio médico), fecha válida desde 1900 y no futura,
nombre no vacío, imagen HTTPS, listas de hasta 50 valores de hasta 80 bytes,
sin duplicados ni un mismo color simultáneamente preferido y evitado. Estos límites
concretan validaciones que el informe no cuantifica. El agregado valida antes de
modificar su estado; una entrada inválida no deja cambios parciales.

## PostgreSQL / Supabase

La migración creada con Supabase CLI es:
supabase/migrations/20261109094310_profile_aggregate.sql

Crea user_profiles, style_preferences y body_measurements. Las preferencias se
guardan una por fila y tipo, como pide el PDF; las medidas tienen relación 1:0..1
con el perfil. user_id es único y referencia auth.users. No duplica cuentas Auth.

Las RPC usan SECURITY INVOKER, search_path vacío y auth.uid(); nunca el userId
enviado por el cliente para decidir propiedad. Tablas con RLS y acceso limitado a
authenticated. Anon no puede ejecutar las RPC. Cambios de preferencias son
atómicos y bloquean la raíz del agregado para evitar escrituras intercaladas.
No hay DROP ni sustitución de tablas existentes. Si los nombres ya existen,
la transacción falla y debe revisarse el esquema antes de aplicarla.

**Instalada en Supabase el 2026-11-09.** Se autorizó la CLI mediante el flujo de
inicio de sesión y se aplicó al proyecto larpiojfyzlqhmxfhbxm después de comprobar
que no existían tablas o funciones con los mismos nombres. La versión
20261109094310 quedó registrada como applied en el historial de migraciones.

Se verificaron en el proyecto real las tres tablas con RLS activo, las RPC de
creación, preferencias y medidas, la atomicidad ante preferencias duplicadas y
la denegación de acceso desde otra identidad y desde anon. Las pruebas de escritura
se hicieron en una transacción revertida: no quedan medidas o perfiles ficticios.
El endpoint de Drogon devuelve 404 profile_not_found para una cuenta sin perfil;
la falta de esquema ya está resuelta.

El asesor de seguridad no informó problemas del nuevo esquema. Informó una
advertencia del proyecto: protección contra contraseñas filtradas deshabilitada;
no se modificó la configuración Auth durante la migración.

Comandos ejecutados desde iam-service, con Supabase CLI 3.0.0:

```text
npx supabase@3.0.0 db query --remote=larpiojfyzlqhmxfhbxm --file supabase/migrations/20261109094310_profile_aggregate.sql --yes
npx supabase@3.0.0 migration repair 20261109094310 --status applied --remote=larpiojfyzlqhmxfhbxm --yes
npx supabase@3.0.0 db advisors --remote=larpiojfyzlqhmxfhbxm --type security
```

La migración no debe volver a ejecutarse: usa CREATE y falla ante objetos existentes.

## Verificación

- Compilación MSVC x64 Debug.
- CTest profile-domain: fechas, NaN, medidas negativas, preferencias duplicadas,
  conservación del estado ante errores, comandos/consultas y propietario.
- python tests/auth_smoke.py: regresión Auth y contratos HTTP de Profile con mock,
  creación/lectura/actualización, IDOR, autenticación y validación de medidas.
- python tests/profile_sql.py: migración en una base local nueva, persistencia,
  rollback de preferencias inválidas, restricciones SQL y aislamiento RLS.
- Supabase real: pruebas SQL en transacción con rollback y comprobación de la ruta
  Profile a través de Drogon con la cuenta de prueba confirmada.

Para la prueba SQL se requiere psycopg2 y un clúster PostgreSQL de pruebas
escuchando solo en 127.0.0.1:55439. El script crea una base nueva, no modifica
Supabase ni una base existente. Mantiene los datos de prueba para inspección.

Generación de avatar, eventos para consumidores externos, provisión automática de
perfil tras Google y permisos de tienda siguen pendientes; no se simulan como éxitos.

## Coordinación de Account, Profile y Preferences

Las rutas HTTP existentes se conservan. AccountService coordina el login de correo,
Google y el registro si devuelve sesión inmediata. AuthCommandService mantiene las
operaciones propias de identidad. ProfileCommandService administra datos personales
mediante el agregado y PreferencesCommandService administra las preferencias del
mismo agregado. Las consultas tienen servicios separados; comparten PostgreSQL.

Un login válido devuelve profile_ready=true después de encontrar o crear el perfil.
No reemplaza nombre, medidas ni preferencias en logins posteriores. Si dos logins
intentan crearlo a la vez, el conflicto único se resuelve releyendo el perfil.
No hay una transacción distribuida entre Supabase Auth y Profile: si la persistencia
falla, se solicita revocar la nueva sesión y se responde 503 sin entregar tokens.
Si el proveedor también falla al revocar, la sesión puede quedar activa hasta sus
límites de expiración, aunque no se haya entregado al cliente. Un nuevo login puede
reintentar la inicialización; no se borra la cuenta para compensar el fallo.

La prueba real de login inicializó el perfil de la cuenta de prueba existente.
Un segundo login conservó su id, fecha de creación, preferencias y medidas. No se
registraron medidas corporales ficticias durante esta prueba.

## Swagger / OpenAPI

Con el servicio iniciado, abrir http://127.0.0.1:8080/docs (alias /swagger).
El contrato está disponible en /openapi.json y en docs/openapi.json del repositorio.
Las 16 operaciones se agrupan en Account, Profile, Preferences y Health.

1. Abrir POST /api/v1/auth/login, pulsar Try it out y usar una cuenta de prueba.
2. Copiar access_token de la respuesta.
3. Pulsar Authorize e introducir solo ese token, sin el prefijo Bearer.
4. Probar GET /api/v1/auth/me y GET /api/v1/profiles/{userId}, usando user.id.
5. Editar los ejemplos de preferencias o medidas antes de enviarlos: Try it out
   llama al proyecto Supabase configurado y guarda los valores enviados.

Google requiere el ID token del flujo nativo de Flutter. Swagger no tiene un
Client Secret de Google ni usa el flujo OAuth web para suplantar ese flujo nativo.

Swagger UI 5.31.0 se sirve desde archivos locales con versión e integridad fijadas
(ver docs/VENDOR.md y docs/LICENSE). No usa un CDN ni un validador externo; el
Bearer se mantiene en memoria y no se conserva tras recargar. La documentación
solo expone una lista explícita de archivos. La descarga estática genérica de
archivos de la carpeta del proceso está deshabilitada.

Los presets Ninja copian docs al directorio del ejecutable mediante CMake. Al
copiar el binario a otra carpeta, copiar también su carpeta docs. Si se modifica
el contrato o el HTML, reconstruir: CMake vuelve a copiar los recursos.

Pruebas adicionales:

```text
ctest --test-dir out/build/x64-debug-vcpkg --output-on-failure
python tests/auth_smoke.py
python tests/openapi_contract.py
```

La interfaz se abrió en un navegador real y se ejecutó GET /health desde Swagger
con respuesta 200. OpenAPI pasó la validación formal y la prueba de correspondencia
con las rutas declaradas en los controladores.
