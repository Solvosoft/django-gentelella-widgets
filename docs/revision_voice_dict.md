# Revisión del branch `voice_dict` (vs `master`)

Guía para que una persona revise y **reproduzca** manualmente la funcionalidad de
dictado por voz con el reconocimiento **local** (Parakeet‑v3 en proceso).

- Branch: `voice_dict`
- Base: `master`
- Alcance: 16 commits, 26 archivos (`git diff --stat master..voice_dict`)

---

## 1. Qué introduce el branch

Dictado de voz (speech‑to‑text) como widgets de formulario Django:

- **`VoiceDictation`** (`djgentelella/widgets/core.py`) — un `<textarea>` con botón de
  micrófono.
- **`VoiceEditorTinymce`** (`djgentelella/widgets/tinymce.py`) — editor TinyMCE con
  botón de micrófono en su propia barra de herramientas.

Ambos capturan audio en el navegador (Web Audio + VAD) y lo transcriben mediante un
endpoint (`VoiceTranscribeView`, `djgentelella:voice_transcribe`) con **dos backends
intercambiables**:

- `local` — corre Parakeet‑v3 en el propio proceso Django (extra `djgentelella[asr]`).
- `remote` — reenvía el audio a un ASR externo compatible con OpenAI
  (`/v1/audio/transcriptions`) o a `voz_procesor`.

Tres estrategias de dictado vía `data-mode`:

| Modo | Comportamiento |
|------|----------------|
| `segments` (por defecto) | Cada frase (cortada en una pausa natural) se transcribe y se inserta en vivo. |
| `single` | No envía nada hasta *Stop*; transcribe toda la grabación en una sola petición. |
| `hybrid` | Muestra segmentos en vivo y, al parar, re‑transcribe todo y reemplaza el preview. |

---

## 2. Inventario de cambios

**Backend (Python)**
- `djgentelella/voice/asr.py` — Parakeet‑v3 local (import perezoso de `onnx_asr`/`av`/`numpy`);
  decodifica a float32 mono 16 kHz y transcribe (pin de `target_language` = idioma origen).
- `djgentelella/voice/views.py` — `VoiceTranscribeView` con selección de backend y
  mapeo de campos para el ASR remoto.
- `djgentelella/urls.py` — ruta `voice/transcribe/` (con `login_required`).
- `djgentelella/widgets/core.py`, `djgentelella/widgets/tinymce.py` — los dos widgets.
- `djgentelella/templates/gentelella/widgets/voice_dictation.html` — plantilla del textarea.
- `pyproject.toml` — extra `voice` (`onnx-asr[cpu,hub]`, `av`, `numpy`).

**Frontend (JS)**
- `static/gentelella/js/base/voiceprogressive.js` — motor progresivo (captura PCM, VAD,
  WAV por segmento, pool de POSTs, reordenado).
- `static/gentelella/js/base/voicedictation.js` — consumidor del textarea.
- `static/gentelella/js/base/voiceeditortinymce.js` — botón/consumidor TinyMCE.
- `static/gentelella/js/base/editorTinymce.js` — se extrae `gentelella_tinymce_config()`
  compartida (refactor: TextareaWysiwyg/EditorTinymce/voz usan la misma config).
- `static/gentelella/js/widgets.js` — registra los plugins `VoiceDictation` y
  `VoiceEditorTinymce`.
- `static/gentelella/js/base/mediarecord.js` — el diálogo de error muestra `error.name`.
- `management/commands/createbasejs.py` — añade los 3 nuevos JS al bundle `base.js`.

**Demo**
- `demo/demo/settings.py` — settings `GENTELELLA_ASR_*` (backend por defecto = **`local`**).
- `demo/demoapp/voice/` (`forms.py`, `views.py`) + `templates/gentelella/voice/inputs.html`
  + rutas `voice/` y `voice/transcribe` en `demo/demoapp/urls.py`.

**Docs**: `docs/source/widgets/voice.rst` (+ referencias en `widgets.rst`, `advancedwidgets.rst`).

---

## 3. Requisitos previos

- Python 3.11–3.13, entorno virtual del proyecto:
  ```bash
  source ~/entornos/djgentelella/bin/activate
  ```
- Navegador con permiso de micrófono. **`getUserMedia` requiere contexto seguro**:
  sirve la página desde `http://localhost` (permitido) o por HTTPS.
- Primera ejecución del backend local: descarga ~670 MB del modelo desde Hugging Face
  (requiere red y espacio en disco). Corre en **CPU**.

---

## 4. Puesta en marcha (reconocimiento LOCAL)

```bash
# 1. Situarse en el branch
git checkout voice_dict

# 2. Instalar el extra de voz (Parakeet local)
pip install -e ".[asr]"          # o: pip install "djgentelella[asr]"

# 3. Regenerar assets estáticos (base.js NO está versionado: es un artefacto de build)
pip install requests
python manage.py loaddevstatic   # descarga librerías front (TinyMCE, etc.)
python manage.py createbasejs    # genera static/.../js/base.js con los 3 JS de voz

# 4. Preparar la demo
make init_demo                   # migrate + createdemo + demomenu + superuser
```

> **Nota `base.js`**: aparece como archivo sin seguimiento (`??`) porque se genera con
> `createbasejs`. Confirma que quedó regenerado:
> ```bash
> grep -c "createProgressiveVoiceEngine\|getVoiceDictation" \
>   djgentelella/static/gentelella/js/base.js   # debe ser > 0
> ```

**Backend por defecto**: en `demo/demo/settings.py`, `GENTELELLA_ASR_BACKEND` toma
`os.getenv('GENTELELLA_ASR_BACKEND', 'local')`, así que **por defecto ya usa el modelo
local**. Para forzarlo explícitamente:

```bash
export GENTELELLA_ASR_BACKEND=local
cd demo && python manage.py runserver
```

Abre **http://localhost:8000/voice/** (inicia sesión con el superusuario si se solicita).

---

## 5. Escenarios de prueba (checklist funcional)

La página `/voice/` muestra el textarea en los 3 modos y el editor TinyMCE.

- [ ] **Permiso de micrófono**: al pulsar *Dictate* el navegador pide permiso; al
      concederlo, el estado pasa a *"Listening..."* y el botón cambia a *Stop and transcribe*.
- [ ] **Modo `segments`** (textarea 1): habla con pausas de ~0.6 s; cada frase aparece
      en vivo, en orden, mientras sigues hablando.
- [ ] **Modo `single`** (textarea 2): nada aparece mientras hablas; al pulsar *Stop* se
      transcribe toda la grabación de una vez.
- [ ] **Modo `hybrid`** (textarea 3): aparecen segmentos en vivo y, al parar, el texto se
      reemplaza por la transcripción completa (a veces distinta de la suma de segmentos).
- [ ] **TinyMCE**: el botón de micrófono está en la barra; el texto se inserta en el
      cursor vía `insertContent`; verifica que **no** se inyecta HTML (escape correcto).
- [ ] **Cancelar**: el botón *Cancel* (textarea) detiene y descarta el preview sin insertar.
- [ ] **Idioma**: transcribe en español (`language='es'`); comprueba que **no** traduce a
      inglés (pin de `target_language`).
- [ ] **Primer uso**: la primera petición tarda (descarga + warm‑up del modelo); las
      siguientes son rápidas.
- [ ] **Error de dispositivo**: sin micrófono / permiso denegado, aparece el diálogo de
      error mostrando el `error.name`.

### Verificación por red/servidor (opcional)
- En las DevTools → Network verás POST a `voice/transcribe`:
  - `segments`/`hybrid`: varias peticiones `segN.wav` (+ `full.wav` en hybrid al parar).
  - `single`: una sola petición `full.wav` al parar.
  - Cada respuesta es `{"text": "..."}`.
- En consola del servidor, la primera petición dispara la carga del modelo.

---

## 6. Checklist de revisión de código

**Backend**
- [ ] `asr.py`: imports perezosos (importar `djgentelella` sin el extra no debe fallar);
      carga del modelo con lock, inferencia sin lock; `decode_to_f32_16k` maneja flush de
      resampler y audio vacío.
- [ ] `views.py`: selección de backend (`local`/`remote`, auto según URL remota);
      `ImportError` → 501, fallo de transcripción → 500, ASR remoto caído → 502;
      `_extract_text` normaliza `{"text"}` y `{"transcription": {"text"}}`.
- [ ] Ruta de `djgentelella` protegida con `login_required`.
- [ ] Manejo del archivo como stream (no copia en memoria del audio).

**Frontend**
- [ ] `voiceprogressive.js`: VAD (RMS, silencio/mín. voz/máx. segmento), WAV a
      **tasa nativa** (no downsample en navegador), pool acotado, reordenado por índice,
      invalidación por `gen` (respuestas tardías al cancelar/parar), teardown de recursos.
- [ ] `voiceeditortinymce.js`: escape HTML antes de `insertContent`; API TinyMCE 5
      (`setDisabled`, no `setEnabled`); `engine.destroy()` en `editor.on('remove')`.
- [ ] Refactor `gentelella_tinymce_config`: TextareaWysiwyg/EditorTinymce mantienen el
      comportamiento previo (misma toolbar/plugins).

**Config / build**
- [ ] `createbasejs.py` incluye los 3 JS y `base.js` se regenera correctamente.
- [ ] `pyproject.toml`: extra `voice` con versiones coherentes.

---

## 7. Observaciones / hallazgos a validar

1. ~~**Aviso desactualizado en la demo**~~ — **RESUELTO**. El `alert` de
   `demo/demoapp/templates/gentelella/voice/inputs.html` decía que el endpoint era un
   *mock*; ya se corrigió para describir el ASR real (`VoiceTranscribeView`, backend según
   `GENTELELLA_ASR_BACKEND`, local por defecto).

2. **Dos endpoints de transcripción** — la demo define su propia ruta `voice-transcribe`
   (sin `login_required`) en `demo/demoapp/urls.py`, mientras `djgentelella` expone
   `voice_transcribe` (con `login_required`). Los formularios de la demo usan la primera.
   Verificar que es intencional (la del paquete sí exige login).

3. **`base.js` no versionado** — es artefacto de `createbasejs`; sin ejecutarlo, la
   funcionalidad de voz no carga. Debe documentarse/ejecutarse en cualquier despliegue.

4. **Parakeet no admite biasing** — `data-hotwords` / `data-initial-prompt` se ignoran en
   el backend local (solo aplican a backends tipo Whisper). Es una limitación conocida y
   aceptada; los nombres propios/acrónimos pueden transcribirse mal.

5. **Coste del primer uso** — descarga de ~670 MB + warm‑up en CPU. Considerar si aplica
   un pre‑cargado del modelo en despliegues reales.

---

## 8. Comandos de referencia rápidos

```bash
# Resumen de cambios
git log --oneline master..voice_dict
git diff --stat master..voice_dict

# Diff por área
git diff master..voice_dict -- djgentelella/voice/
git diff master..voice_dict -- 'djgentelella/static/gentelella/js/base/voice*'

# Tests del paquete
cd demo && python manage.py test djgentelella.tests -v2
```
