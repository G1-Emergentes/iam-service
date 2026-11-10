# SAM 3D Body — preparación local

La cuenta de Hugging Face ya fue autenticada en esta PC mediante autorización
en navegador (`hf auth login`). Las credenciales las administra la CLI en su
caché de usuario; no se guardan en Mirage, Flutter, `.env` ni este documento.
No se contrata un Inference Endpoint ni se requiere un plan de pago.

Modelo elegido: `facebook/sam-3d-body-vith`.
Revisión: `f7f4ba4f67739e297f291639afb7c59041745367`.

Desde `iam-service`:

```powershell
./avatar-worker/download-sam.ps1 -CheckOnly
./avatar-worker/download-sam.ps1
```

El script usa `huggingface_hub==2.4.0` en un entorno de herramientas aislado de
uv. Descarga los cinco archivos oficiales (unos 2.4 GB) en
`avatar-worker/models/sam-3d-body-vith/`, ignorado por Git. Comprueba los tamaños
de `model.ckpt` y `assets/mhr_model.pt` al finalizar y conserva LICENSE y README.
Se puede reejecutar para reanudar una descarga; no borra ni sobrescribe el código
del worker actual y no usa `--force-download`.

Si la sesión de Hugging Face deja de estar disponible, autorizar de nuevo con:

```powershell
uv tool run --from huggingface_hub==2.4.0 hf auth login --no-add-to-git-credential
```

No pegar tokens en comandos, chats, Flutter ni archivos del proyecto.

## Prueba de inferencia en esta PC

Comprobada en Windows con Python 3.11.14, PyTorch 2.8.0+cu128 y RTX 4060 Ti
de 8 GB. Dos ejecuciones sobre la imagen oficial produjeron una malla finita
de 18 439 vértices y 36 874 triángulos. La segunda tardó 6.18 s cargando el
modelo y 2.27 s en inferencia, con 3043.8 MiB asignados y 3176 MiB reservados
de VRAM. Son resultados de una imagen, no una garantía para cualquier foto.

Se usa el código oficial sin modificar, commit
`b5c765a0d89d789985e186d396315e7590887b94`, en `.sam-source`, y un entorno
`.sam-venv` separado del worker CPU. Comandos ejecutados desde `iam-service`:

```powershell
uv venv --python 3.11 avatar-worker/.sam-venv
git clone --depth 1 https://github.com/facebookresearch/sam-3d-body.git avatar-worker/.sam-source
uv pip install --python avatar-worker/.sam-venv/Scripts/python.exe torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu128
uv pip install --python avatar-worker/.sam-venv/Scripts/python.exe -r avatar-worker/sam/requirements.in
./avatar-worker/.sam-venv/Scripts/python.exe avatar-worker/sam/probe.py
```

La clonación anterior ya está hecha; no repetirla sobre la carpeta existente.
En una instalación nueva, fijar el commit indicado con `git -C
avatar-worker/.sam-source checkout b5c765a0d89d789985e186d396315e7590887b94`
(si no está en el clon superficial, obtenerlo antes con `git fetch origin
b5c765a0d89d789985e186d396315e7590887b94`). `sam/requirements.lock` conserva
las versiones probadas. Para recrear exactamente las dependencias, usar ese
archivo en lugar de `requirements.in`, agregando
`--extra-index-url https://download.pytorch.org/whl/cu128`.

Para repetir ahora basta el último comando. Puede aceptar una imagen local
con `--image RUTA`. Guarda la imagen, predicción, GLB e informe en
`avatar-worker/output/sam-probe`, ignorado por Git. Usar solo imágenes para las
que se tenga autorización; esta prueba conserva sus entradas y resultados.

Para ver el resultado, servir únicamente esa carpeta, sin publicar el proyecto:

```powershell
./avatar-worker/.sam-venv/Scripts/python.exe -m http.server 8092 --bind 127.0.0.1 --directory avatar-worker/output/sam-probe
```

Abrir http://127.0.0.1:8092. La vista usa los archivos Babylon locales existentes.
Se verificó en navegador que carga la imagen y la malla. No es una API para Flutter.

La ruta usa MHR TorchScript y omite Flash Attention y Momentum. El cargador
oficial emite advertencias de claves MHR/manos ausentes con `strict=False`;
no se han silenciado ni modificado los pesos. La malla se comprobó para esta
imagen; no se validó precisión de manos, formas o antropometría.

## API local para Flutter

`./avatar-worker/run-sam-mobile.ps1` inicia el servidor loopback en el puerto
8093, usando el entorno CUDA separado. Requiere las dependencias actualizadas
de `sam/requirements.in` (FastAPI, uvicorn y python-multipart incluidas).

`POST /api/reconstructions` recibe `photo`, `height_cm` y `weight_kg` multipart.
Devuelve un UUID y HTTP 202; `GET /api/reconstructions/{id}` consulta su estado.
`GET /api/reconstructions/{id}/model.glb` descarga la malla y `/view/{id}` la
muestra con Babylon local. `DELETE /api/reconstructions/{id}` descarta un
trabajo terminado. Las fotos se validan con los límites del worker existente,
se eliminan EXIF/GPS y los archivos temporales se limpian incluso al fallar.

Una sola inferencia por vez y dos trabajos retenidos; caducan en diez minutos.
La API de Flutter ahora crea una pose neutra MHR y escala por altura declarada;
devuelve estimaciones geométricas de pecho, cintura y cadera. Hombros queda
manual. Son proxies por secciones relativas, sin validación antropométrica.
El proceso vuelve a cargar SAM por trabajo para liberar VRAM al terminar;
la latencia completa incluye arranque/importaciones, no solo inferencia.

Los previews temporales usan identificadores aleatorios como capacidades
locales. Guardar/ajustar/reabrir exige bearer validado por IAM, dueño del trabajo
y RLS con sesión activa. Sigue escuchando solo loopback: no exponerlo en red.
Antes de desplegar falta un gateway y autorización para los previews también.

`POST /api/reconstructions/{id}/adjust` recibe medidas y fitPreference, devuelve
otro trabajo que regenera la geometría desde el JSON. `PUT .../{id}/profile`
guarda foto privada + receta en Supabase. `POST /api/avatar/open` regenera el
avatar guardado; `GET /api/avatar/photo` recupera la foto propia autenticada.
La migración `20261110000127_avatar_body_profile.sql` crea tabla y políticas.
La configuración usa solo SUPABASE_URL y SUPABASE_PUBLISHABLE_KEY del `.env`
existente. No necesita service_role ni contraseña PostgreSQL.

## Pendiente de calibración

Tener los pesos descargados no habilita automáticamente la estimación. La prueba
de inferencia debe usar un entorno separado del Anny/PyTorch CPU existente.
La receta oficial propone Python 3.11 y PyTorch; el estimador trabaja en CUDA.
La prueba anterior confirma que la ruta corporal cabe en esta GPU.

Para una primera prueba de una sola persona y cuerpo completo, el estimador
oficial permite usar la imagen completa sin detector, segmentador ni estimador
de campo de visión. Esto evita instalar Detectron2/SAM3/MoGe antes de necesitar
esas capacidades. No significa que automáticamente valide postura o encuadre.

El modelo produce un cuerpo MHR, distinto de Anny. La escala declarada, pose
neutra y contornos geométricos están implementados, pero aún requieren
comparación con mediciones reales. No deben publicarse como medidas exactas.

El endpoint antiguo `/api/estimations` del worker CPU continúa deshabilitado;
Flutter usa `/api/reconstructions` en el proceso CUDA. Falta validar precisión
con cinta métrica, detectar fotos mal encuadradas y robustez frente a ropa
holgada. El peso no se utiliza para inventar perímetros.

Referencias oficiales:

- https://github.com/facebookresearch/sam-3d-body
- https://github.com/facebookresearch/sam-3d-body/blob/main/INSTALL.md
- https://huggingface.co/facebook/sam-3d-body-vith
