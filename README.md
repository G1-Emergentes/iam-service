# Mirage IAM Service

API C++17 con Drogon para identidad, sesiones y perfil de Mirage (ReWear).
Supabase gestiona Auth, PostgreSQL y el almacenamiento privado de fotografías.
El worker Python del avatar vive en `avatar-worker/` y se ejecuta como proceso separado.

## Desarrollo local

Requisitos: Visual Studio con herramientas C++ x64, CMake, Ninja y Drogon instalado
con vcpkg para `x64-windows`. Ejecutar desde una consola de desarrollo x64 de Visual Studio.
Sustituir la ruta de vcpkg por la instalación local:

```powershell
cmake --preset x64-debug -DCMAKE_TOOLCHAIN_FILE=C:/dev/vcpkg/scripts/buildsystems/vcpkg.cmake -DVCPKG_TARGET_TRIPLET=x64-windows
cmake --build out/build/x64-debug-vcpkg
Copy-Item .env.example .env
```

Completar `.env` localmente con la URL y publishable key de Supabase. Si ya existe,
conservarlo. No se necesita la contraseña PostgreSQL ni una service_role key para
ejecutar el servidor.

```powershell
./run-auth.ps1
```

- Estado: `http://127.0.0.1:8080/health`
- Swagger: `http://127.0.0.1:8080/docs`
- Contrato: `http://127.0.0.1:8080/openapi.json`

Las migraciones versionadas están en `supabase/migrations/`.
El worker del avatar tiene su propia instalación: consultar
[SAM_SETUP.md](avatar-worker/SAM_SETUP.md) y [README](avatar-worker/README.md).
Los pesos se descargan desde el proveedor tras obtener acceso; no se distribuyen
en este repositorio. SAM requiere el entorno CUDA descrito en esa documentación.

## Documentación

- [Auth y API](AUTH.md)
- [Perfil, medidas y DDD/CQRS](PROFILE.md)
- [Recuperación y sesiones](RECOVERY.md)

## Archivos locales

Git excluye credenciales, fotografías subidas, salidas generadas, compilados,
entornos Python y pesos del modelo. Conservar las licencias de las dependencias.
El repositorio contiene código y configuración de ejemplo, no datos de usuarios.

El despliegue público todavía requiere configurar HTTPS, red, secretos del entorno
y un alojamiento GPU para SAM. Los scripts actuales describen el desarrollo local.
