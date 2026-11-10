# Mirage Auth Service

Recuperación, reenvío y sesiones: ver RECOVERY.md. Se añadieron resend-verification
y verify-email; Swagger documenta ahora 18 operaciones. Logout se comprueba también
contra auth.sessions y reset-password exige sesión activa y cierra todas las
sesiones al terminar. El flujo local de correo vuelve a /auth/callback.

Actualización DDD/CQRS: Auth ahora está separado de su adaptador HTTP/Supabase.
El servicio también incluye el bounded context Profile del PDF con entidad,
agregado, preferencias y medidas corporales. Ver PROFILE.md para estructura,
rutas y pruebas. La migración 20261109094310 está instalada y verificada en Supabase.

Estado: implementado, probado contra un proveedor simulado y conectado al proyecto
real de Supabase. El 2026-11-09, GET /auth/v1/settings devolvió 200 con la publishable
key y GET /api/v1/auth/me mediante Drogon rechazó un token inválido con 401.
GET /health devolvió 200. Google y Email están habilitados. Se creó una cuenta de
prueba con autorización del usuario y el usuario confirmó la recepción del correo
SMTP y abrió el enlace desde su teléfono. La cuenta quedó confirmada. Login, /me,
refresh y logout con Supabase real devolvieron 200. Las credenciales de prueba se
guardan exclusivamente en .env.auth-test, excluido de Git; no se guardan tokens.
Falta probar Google con una identidad real y configurar la redirección final a una
URL accesible desde el teléfono: la página posterior a confirmar no cargó.

## Requisitos del informe

Fuente: informe ReWear proporcionado por el usuario, 191 páginas. Se extrajo el
texto completo y se revisaron las secciones de identidad, historias, seguridad,
arquitectura, modelo de datos y flujos. También se inspeccionaron visualmente las
páginas 105 y 110 para contrastar los diagramas con el texto.

| Referencia | Requisito | Implementación / dependencia |
| --- | --- | --- |
| EP01, pp. 49-50 | Identidad, perfil y preferencias | Módulos Auth y Profile separados dentro del mismo servicio; ver PROFILE.md. |
| US01, pp. 50-51 | Registro con nombre, correo, contraseña o Google; verificación por correo | Signup de Supabase con display_name; Google mediante ID token. Configurar Email y Google en Supabase. |
| US02, p. 51 | Login por correo o Google; rechazar credenciales inválidas | Endpoints login y google delegan la validación a Supabase. |
| US03, pp. 51-52 | Recuperación por correo y nueva contraseña | Endpoints forgot-password y reset-password. La app recibe el enlace de recuperación y proporciona el access token de recuperación. |
| US04, p. 52 | Cerrar sesión e invalidar autenticación | Logout local revoca la sesión de refresh en Supabase. Ver limitación de access tokens abajo. |
| US18, pp. 58-59 | Cuenta comercial, datos fiscales únicos | Requiere el contexto Store y validación comercial; no se acepta un rol enviado por el cliente al registrarse. |
| Seguridad, pp. 76-77 y 81-82 | Bloquear tras 5 fallos en menos de 2 minutos | Límite local más estricto: 5 intentos totales por IP/120 segundos, compartido entre login y Google. |
| Arquitectura, p. 105 | Flutter/Angular, API Gateway y Auth Service; PostgreSQL independiente | Drogon funciona como API de Auth; Supabase Auth persiste identidad en PostgreSQL. Gateway y otros servicios quedan separados. |
| Datos, pp. 106-110 | Cuenta 1:1 perfil; preferencias y medidas | auth.users identifica la cuenta con UUID. No se duplican contraseñas en tablas públicas. Perfil/tienda podrán referenciar ese UUID. |
| Wireflow, p. 167 | Aparece Apple además de Google | Apple no aparece en US01/US02: requiere aclarar el alcance antes de añadirlo. |

## Decisiones y diferencias con el informe

- El usuario eligió Supabase Auth + Drogon. Supabase gestiona contraseñas, correo,
  identidades Google y tokens. El servicio no firma JWT propios.
- US01/US03 piden revelar si un correo existe. El servicio usa mensajes genéricos
  y conserva la protección de Supabase contra enumeración. El resultado de signup
  no debe utilizarse para deducir si el correo ya estaba registrado.
- El informe deja abierta la duración y el criterio del bloqueo. Se eligió IP y
  una ventana de 120 segundos. El sexto intento dentro de esa ventana recibe 429.
  Es un límite en memoria por proceso: al reiniciar se pierde; con réplicas hace
  falta almacenamiento compartido. Detrás de un proxy se verá su IP hasta configurar
  una estrategia de proxies de confianza; no se confía en X-Forwarded-For del cliente.
- Logout revoca la sesión actual y Mirage comprueba su existencia en auth.sessions.
  Profile también exige sesión activa mediante RLS. Los microservicios/gateway
  futuros deberán usar esa comprobación para extender la revocación inmediata;
  verificar solo la firma del JWT no basta. Ver RECOVERY.md.
- La promoción a tienda pertenece a un flujo autorizado de negocio; display_name
  es metadata editable y nunca se usa para decidir permisos.

## API

Todas las rutas de identidad comienzan en /api/v1/auth. Responden JSON y
Cache-Control: no-store. /health permanece disponible sin configurar Supabase.

| Método y ruta | Entrada |
| --- | --- |
| POST /register | {"name":"Ana","email":"ana@example.com","password":"a-strong-password"} |
| POST /login | {"email":"ana@example.com","password":"a-strong-password"} |
| POST /google | {"id_token":"GOOGLE_ID_TOKEN","nonce":"nonce-si-el-flujo-lo-utiliza"} |
| POST /refresh | {"refresh_token":"REFRESH_TOKEN"} |
| GET /me | Authorization: Bearer ACCESS_TOKEN |
| POST /logout | Authorization: Bearer ACCESS_TOKEN |
| POST /forgot-password | {"email":"ana@example.com"} |
| PUT /reset-password | Authorization: Bearer ACCESS_TOKEN; {"password":"a-new-strong-password"} |
| POST /resend-verification | {"email":"ana@example.com"} |
| POST /verify-email | {"email":"ana@example.com","token":"12345678","type":"signup"} |

Google requiere un ID token real obtenido por Flutter mediante Google Sign-In;
Supabase valida emisor y audiencia. nonce es opcional y debe coincidir con el usado
al obtener el token. No se acepta un correo como prueba de identidad Google.

Los éxitos conservan el JSON de Supabase (user/access_token/refresh_token según
el endpoint); signup puede no devolver sesión hasta verificar el correo. Login
debe manejar ese caso sin asumir que ya existe una sesión. Logout devuelve {}.
Los errores locales/proveedor tienen forma {"error":"codigo"}. Los fallos de
credenciales devuelven 400 o 401; el consumidor debe manejar ambos.
503 significa configuración ausente/inválida; 502 proveedor inaccesible; 429 límite.
Las llamadas salientes son asíncronas, con timeout de 10 segundos y TLS verificado.

## Configurar Supabase

1. Crear el proyecto y obtener Project URL y publishable key. No hace falta usar
   secret/service_role ni la contraseña PostgreSQL en este servicio.
2. Activar Email con confirmación y una política de contraseña acorde (mínimo 8).
   Configurar Site URL y Redirect URLs para la app Flutter y la página de recuperación.
3. Configurar SMTP propio para correos reales y revisar los límites de envío.
4. Activar Google y configurar los client IDs/audiencias de Google Sign-In para
   Flutter. Verificar en un dispositivo el flujo completo con un ID token real.
5. Revisar expiración de access tokens y límites del proveedor. Las peticiones del
   servicio comparten IP de salida; tenerlo en cuenta al configurar límites.
6. Guardar los refresh tokens en almacenamiento seguro de la app. Servir esta API
   mediante HTTPS en despliegue. No registrar credenciales o tokens.

No hay SQL de cuentas adicional: Supabase Auth crea y gestiona su esquema auth.
Al añadir perfiles o tiendas en un esquema expuesto se deberán definir RLS y
permisos basados en el UUID autenticado antes de exponer datos.

## Ejecutar

PowerShell, desde la carpeta iam-service. run-auth.ps1 carga las dos variables de
Supabase desde .env (excluido de Git) y ejecuta el servidor compilado:

```powershell
.\run-auth.ps1
```

En otra máquina, copiar .env.example a .env y completar los valores. También se
pueden definir las variables directamente y ejecutar el binario:

```powershell
$env:SUPABASE_URL = 'https://YOUR-PROJECT.supabase.co'
$env:SUPABASE_PUBLISHABLE_KEY = 'YOUR-PUBLISHABLE-KEY'
.\out\build\x64-debug-vcpkg\iam-service.exe
```

Para compilar, usar el entorno Developer Command Prompt x64 de Visual Studio,
con su CMake y Ninja disponibles:

```text
cmake --preset x64-debug
cmake --build out/build/x64-debug-vcpkg
python tests/auth_smoke.py
```

En Visual Studio las variables deben estar disponibles en el entorno del proceso
de depuración; también se puede abrir Visual Studio desde la consola configurada.
Si TLS no encuentra las CA en Windows, configurar un almacén CA válido para
OpenSSL. Nunca desactivar validación de certificados para resolverlo.

Las pruebas ocupan temporalmente 8080 y un puerto local aleatorio para el mock.
Verifican contratos REST, JSON inválido, tamaño, campos permitidos, autenticación,
redacción de errores, límites y falta de configuración. No verifican correo real,
Google real, firmas JWT ni revocación del proveedor. No usar python -O: elimina asserts.

## Fuentes técnicas

- https://supabase.com/docs/guides/auth/passwords
- https://supabase.com/docs/guides/auth/social-login/auth-google
- https://supabase.com/docs/guides/auth/sessions
- https://github.com/supabase/auth (contratos REST del proveedor)
- Headers de Drogon 1.9.14 instalados mediante vcpkg en esta máquina.
