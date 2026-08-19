# Quickstart

Clean install to run the demo locally. See `README.rst` for using djgentelella
inside your own project.

```bash
git clone https://github.com/Solvosoft/django-gentelella-widgets.git
cd django-gentelella-widgets
python -m venv .venv && source .venv/bin/activate

pip install -r requirements.txt

make patch-pylp    # Python 3.12+ compat fix for the pylp build tool (pulls test_requirements.txt too)
make loadstatic    # download vendor JS/CSS (needs internet)
make basejs        # generate djgentelella/static/gentelella/js/base.js
make assets        # build djgentelella's own bundles + collectstatic

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
