# Correo, recuperación y sesiones

## API

Todas las rutas comienzan con /api/v1/auth:

| Método y ruta | Entrada | Resultado |
| --- | --- | --- |
| POST /resend-verification | email | Mensaje genérico; envía solo si la confirmación está pendiente |
| POST /verify-email | email, token, type: signup o recovery | Valida el código y devuelve sesión con perfil preparado |
| POST /forgot-password | email | Mensaje genérico y envío del correo de recuperación |
| PUT /reset-password | password y Bearer activo | Cambia contraseña y cierra todas las sesiones |

Los códigos son numéricos, de 6 a 10 dígitos y de un solo uso. El proyecto emite
8 dígitos. Un código inválido/usado/caducado devuelve 400 o 401, nunca una sesión.
El reenvío no revela si la cuenta existe. Se conservan los límites de Supabase
para correos y verificaciones. Swagger documenta las 18 operaciones del servicio.

## Recuperación sin Flutter

Abrir http://127.0.0.1:8080/auth/recovery desde el PC del servidor, solicitar el
correo y abrir su enlace desde ese mismo PC. Supabase verifica el enlace y
redirige a /auth/callback; allí se introduce la nueva contraseña. La confirmación
de registro también vuelve a esa ruta y muestra el resultado.

Solo se cambió auth.site_url en Supabase, de localhost:3000 a:

```text
http://127.0.0.1:8080/auth/callback
```

SMTP, Google, MFA y límites no se modificaron. supabase/config.toml versiona
únicamente ese campo; no contiene credenciales SMTP ni claves administrativas.
Antes de publicarlo se deberá configurar el destino real, HTTPS o el enlace
profundo de Flutter. En el teléfono 127.0.0.1 apunta al propio teléfono: se puede
leer allí el correo, pero el enlace local debe abrirse desde el PC.

Las plantillas actuales conservan el enlace estándar de Supabase. Los ejemplos
opcionales en supabase/templates/ muestran cómo incluir códigos visibles; no se
instalaron automáticamente. /auth/verify y /auth/recovery admiten también códigos
cuando la plantilla los incluya.

La página elimina inmediatamente el fragmento con tokens del historial, comprueba
la sesión en el backend y conserva el token solo en memoria. No usa almacenamiento
local ni muestra tokens. Incluye CSP, no-store y Referrer-Policy: no-referrer.
Al completar el cambio limpia y oculta el formulario, y pide iniciar sesión.

## Revocación inmediata

El adaptador valida la identidad mediante Supabase /auth/v1/user y después llama
public.mirage_session_active() con el mismo Bearer. Comprueba session_id, propietario
y not_after en auth.sessions. Una comprobación fallida deniega acceso.

La política RLS de user_profiles exige también sesión activa; las de preferencias
y medidas requieren un perfil visible y heredan esa condición. Un token cerrado
tampoco puede consultar esos datos directamente por REST, aunque siga firmado.

La única función SECURITY DEFINER nueva vive en mirage_private, con search_path
vacío, y devuelve solo un booleano sobre la sesión del propio usuario. No concede
SELECT de auth.sessions a authenticated. La función pública es SECURITY INVOKER;
anon no puede ejecutarla.

Logout cierra únicamente la sesión actual. Otra sesión de la misma cuenta sigue
activa. Reutilizar el access token cerrado devuelve 401 en Mirage y el refresh
token es rechazado por Supabase. Los microservicios/gateway futuros deberán usar
esta comprobación: verificar solo la firma JWT no da revocación inmediata.
No se cambia el comportamiento de los endpoints internos de Supabase Auth.

Reset-password exige sesión activa, cambia la contraseña y solicita logout global.
Devuelve reauthentication_required=true. Si el cambio ocurrió pero no se pudo
confirmar la revocación, devuelve 503 password_changed_session_revocation_failed;
el cliente debe informar que la contraseña ya cambió. No hay rollback distribuido
de contraseñas del proveedor.

Migración aplicada y registrada: 20261109153938_active_sessions.sql.

## Verificación

- CTest: guardas de sesión, comandos de correo, cierre global y fallo parcial,
  además de las pruebas existentes del dominio y coordinación.
- HTTP simulado: códigos inválidos/usados, reenvío, recuperación, refresh revocado
  y fallo de la comprobación de sesión. Contrato OpenAPI alineado con las rutas.
- PostgreSQL local: migraciones, persistencia, atomicidad y RLS tras revocación.
- Supabase real: logout de una de dos sesiones mantuvo la otra activa; el token
  cerrado fue rechazado por Mirage y no pudo leer Profile mediante Data API.
- Recuperación real con un código generado por la API administrativa para la
  cuenta de pruebas: un solo uso, cambio de contraseña, cierre global, rechazo de
  contraseña anterior y login nuevo. La clave administrativa se usó solo en memoria
  del script, nunca como credencial de la aplicación.
- Reenvío real: misma respuesta para la cuenta confirmada y una inexistente. No se
  creó otra cuenta sin confirmar solo para probar el envío de esa variante.
- Supabase aceptó un correo real de recuperación al buzón de pruebas; no se verificó
  automáticamente su recepción ni la apertura del destinatario.
- Navegador con respuestas simuladas: fragmento eliminado y formulario completado.
- Sin advertencias nuevas del esquema en el asesor de seguridad. Persiste el aviso
  previo sobre protección de contraseñas filtradas deshabilitada.

La prueba cambió solo la contraseña de la cuenta Mirage creada para pruebas, no
la de Gmail. La actual quedó en .env.auth-test y su candidato en
.env.auth-test.pending-reset, ambos excluidos de Git. No se guardaron JWT ni códigos.

La prueba real requiere autorización explícita porque cambia esa contraseña:

```text
python tests/auth_live_recovery.py --allow-password-change --project-ref TU_PROJECT_REF
```

Agregar --send-test-email solicita un correo real al buzón de pruebas. Requiere
Supabase CLI 3.0.0 autenticada y el archivo de cuenta de pruebas. No ejecutarlo
contra una cuenta personal de uso normal.

Fuera de este paso: Google real desde Flutter, permisos de tienda y ajustar el
límite local de cinco intentos totales a cinco fallos en dos minutos.
