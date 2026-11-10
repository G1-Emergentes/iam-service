# Mirage avatar worker — primera versión local

No necesita API keys, tokens de Hugging Face ni servicios de inferencia de pago.
Python 3.12, Anny 0.6.2, PyTorch CPU, SciPy, Trimesh y FastAPI. Los recursos del visor
Babylon.js 9.35.0 están guardados localmente; no se descargan al abrir la página.

## Instalar y arrancar (PowerShell, desde iam-service)

```powershell
py -3.12 -m venv avatar-worker/.venv
avatar-worker/.venv/Scripts/python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.15.0+cpu
avatar-worker/.venv/Scripts/python.exe -m pip install -r avatar-worker/requirements.lock
./avatar-worker/run.ps1
```

Visor: http://127.0.0.1:8091/ — Swagger: http://127.0.0.1:8091/docs

El primer modelo se prepara en `avatar-worker/.cache/`. Los resultados locales se
guardan en `avatar-worker/output/`; ambas carpetas y el entorno están ignorados.
Las medidas permanecen en esta PC. No introduzcas datos reales en una PC compartida.
No cambies el binding a `0.0.0.0` ni publiques este prototipo sin autorización.

## Qué hace

- POST `/api/jobs`: valida cinco medidas en centímetros y acepta un trabajo (202).
- GET `/api/jobs/{id}`: estado pending/running/succeeded/failed y resultado.
- GET `/api/jobs/{id}/model.glb`: archivo de un trabajo terminado.
- Un hilo de procesamiento, como máximo dos trabajos admitidos simultáneamente
  (uno ejecutándose y otro pendiente); los demás reciben 429.
- Los trabajos interrumpidos se marcan como fallidos al reiniciar. Los terminados
  conservan su metadata y su GLB. La UI permite volver a generar.
- Malla nativa Anny, cuerpo adulto neutral. Altura por escala uniforme; cuatro
  deformaciones de contornos y dos de torso se ajustan por mínimos cuadrados
  dentro de [-1, 1], con una penalización pequeña de deformaciones extremas.
- Informa medidas solicitadas, aproximaciones de la malla y errores. La tolerancia
  de 3 cm es solo un indicador del ajuste numérico, no precisión antropométrica.

## Límites del modelo

Hombros se aproximan con puntos COCO; cintura usa el recorrido de Anny. Pecho y
cadera usan secciones a alturas relativas 0.72 y 0.52, sin calibración anatómica.
No equivalen necesariamente a la definición de una medición con cinta. Algunos
valores admitidos no se pueden alcanzar con estas seis deformaciones.

Todavía no estima medidas desde fotografías, no reproduce el rostro, no genera ropa ni
simula ajuste físico. Es una malla estática, sin rig exportado ni texturas.

## Captura y preguntas guiadas

La página ofrece modos separados **Con una foto** y **Con mis medidas**.
El flujo fotográfico permite cargar JPEG/PNG/WebP o usar la cámara con permiso.
Pregunta altura (cm/m) y peso (kg/lb), convierte a centímetros/kilogramos y pide
confirmación antes de enviar. Son preguntas guiadas por código; no usa un LLM.

POST `/api/estimations` acepta multipart con `photo`, `height_cm`, `weight_kg`.
La altura admitida es 130–220 cm y el peso 30–250 kg. Se limita el cuerpo multipart
completo, incluso sin Content-Length; la imagen debe pesar como máximo 8 MiB,
medir al menos 256 × 256 píxeles y tener como máximo 20 megapíxeles. Se verifica
el contenido real, se rechazan animaciones, se aplica orientación EXIF, se
redimensiona a un máximo de 2560 píxeles por lado y se descartan los metadatos.

`PhotoEstimationRequest` contiene la foto normalizada y los datos declarados.
`EstimateMeasurements` delega al puerto `BodyEstimator`. El adaptador SAM aún no
carga pesos y devuelve HTTP 503, `sam_access_pending`, sin medidas inventadas.
No crea un trabajo eternamente pendiente ni sustituye silenciosamente la foto
por el modo manual.

No se conserva la foto en `output/` ni en la base de datos. El parser puede usar
un archivo temporal del sistema durante la recepción; se cierra al responder.
La vista previa sigue en memoria del navegador hasta descartarla o cerrar la
página. El botón **Descartar foto y datos** libera esa selección. La cámara se
cierra al capturar, cambiar de modo o salir de la página.

Al continuar manualmente se copia solo la altura declarada; los otros cuatro
campos quedan vacíos. Esta etapa no evalúa pose ni encuadre, ni infiere medidas,
ni guarda datos del perfil. Fotos y peso no se envían a servicios externos.

La cámara requiere HTTPS o localhost. Abrir `127.0.0.1` desde otro dispositivo no
conecta con la PC; la publicación con autorización de Drogon sigue pendiente.

## Relación con el IAM

Esta entrega implementa la prueba local del modelo y su visor. Todavía no publica
las rutas `/api/v1/profiles/{userId}/avatar`, no modifica Supabase y no guarda una
referencia en el perfil. La integración seguirá pasando por autorización de
Drogon y AvatarOrchestrator; nunca se expondrá el worker directamente a Flutter.
El binding loopback y la comprobación de Origin/Host no sustituyen autenticación.

## Comprobaciones

```powershell
avatar-worker/.venv/Scripts/python.exe -m pytest avatar-worker/test_worker.py avatar-worker/test_estimation.py -q
avatar-worker/.venv/Scripts/python.exe avatar-worker/check_model.py
```

La segunda comprobación genera una malla real, comprueba el contenedor GLB y
devuelve los errores de ajuste de una muestra, sin necesitar Supabase.

## Procedencia y licencias

- Anny: https://github.com/naver/anny — Apache-2.0. Recursos nativos MakeHuman/MPFB2:
  CC0; se conservan los avisos del paquete. Se usa exclusivamente `topology=anny`
  y `rig=anny`; no se descargan variantes SMPL/SMPL-X ni sus assets restringidos.
- Babylon.js y loaders 9.35.0: https://github.com/BabylonJS/Babylon.js — Apache-2.0;
  copia del aviso en `static/BABYLON-LICENSE.txt`.
- No se necesita entrenar ningún modelo para ejecutar esta versión.
