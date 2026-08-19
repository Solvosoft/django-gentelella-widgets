# Quickstart

Clean install to run the demo locally. See `README.rst` for using djgentelella
inside your own project.

```bash
git clone https://github.com/Solvosoft/django-gentelella-widgets.git
cd django-gentelella-widgets
python3.13 -m venv .venv && source .venv/bin/activate
# any Python 3.11+ works (README's Requirements) -- 3.13 pinned here to match
# the PyCharm run configs below and what this guide was tested against.
# No python3.13 on your system? Install it or swap in your own 3.11+.

pip install -r requirements.txt

make loadstatic    # download vendor JS/CSS (needs internet)
make basejs        # generate djgentelella/static/gentelella/js/base.js
make assets        # build djgentelella's own bundles + collectstatic
                   # (pulls in patch-pylp automatically; MUST run after
                   #  loadstatic + basejs -- it bundles what they produce,
                   #  and silently skips writing anything if they haven't
                   #  run yet, no error)

make init_demo     # demo DB: migrate, demo data, superuser (asks for credentials)
make run           # http://127.0.0.1:8000
```

`make help` lists every other target (tests, lint, MailHog, translations, release).

`requirements.txt` already covers the `[firmador]` and `[asr-remote]` extras.
The only one it deliberately leaves out is `[asr]` (in-process voice dictation
-- downloads a ~670 MB model on first use):

```bash
pip install -e ".[asr]"
```

## Support services

```bash
make services       # MailHog only (SMTP :1025, UI :8025) -- captures async_notification email
make services-sign  # MailHog + Firmador (digital signature server, :9001)
```

Ctrl+C stops and removes the containers. `services-sign` needs the
`firmadorlibreserver` image built locally first -- see
[docs/source/firmador-setup.rst](docs/source/firmador-setup.rst) for the
two-repo Maven build and the desktop signing agent download.

## Tests

```bash
pip install -r requirements.txt -r test_requirements.txt

make test                 # everything except selenium
make lint                 # pycodestyle + ruff
make lint-fix             # auto-apply the mechanical fixes

make services              # selenium suite drives MailHog for real -- runs in
                            # the foreground, use another terminal for what's next
make test-selenium         # ... inside Xvfb (no display needed)
make test-selenium-run     # ... on your own display, for watching it fail
```

`djgentelella.tests` and `djgentelella.blog.tests` live outside `demo/`, so
discovery doesn't reach them on its own -- this is what CI runs to cover them
too:

```bash
cd demo
python manage.py test --exclude-tag=selenium
python manage.py test djgentelella.tests
python manage.py test djgentelella.blog.tests
```

## PyCharm run configurations

`make run` covers most work from a terminal; these are the two Run/Debug
configurations for running the demo from PyCharm instead. Interpreter is the
project's `.venv` in both.

**main** -- plain WSGI dev server, everything except digital signature:

| Field | Value |
|---|---|
| Script | `demo/manage.py` |
| Script parameters | `runserver 9022` |
| Working directory | `demo/` |
| Environment variables | `PYTHONUNBUFFERED=1` |

**asgi** -- gunicorn + uvicorn worker, needed for `firmador_digital`
(websockets don't work under `runserver`):

| Field | Value |
|---|---|
| Module name | `gunicorn` |
| Parameters | `-c djgentelella/firmador_digital/gunicorn/config_asgi.py` |
| Environment variables | `PYTHONUNBUFFERED=1` |

The gunicorn config hardcodes `demo.asettings` as `DJANGO_SETTINGS_MODULE` and
binds `127.0.0.1:9022` (`UVICORN_BIND`) -- same port as **main**, so run
either one, not both, and switch to **asgi** only when testing signing (after
`make services-sign`, see above).
