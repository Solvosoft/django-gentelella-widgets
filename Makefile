.PHONY: help clean clean-pyc clean-build list test docs release sdist fuzzysdist \
	lint lint-fix test-selenium test-selenium-run run run-mailhog \
	migrate menu init_demo notification_demo validate-mailhog loadstatic basejs assets \
	patch-pylp services services-sign process-loop \
	coverage coverage-all coverage-unit coverage-selenium coverage-selenium-run \
	coverage-report coverage-clean

version = $(shell python djgentelella/__init__.py)

help:
	@echo "-- Run / demo --"
	@echo "run - run the demo dev server (PORT=8000 by default)"
	@echo "run-mailhog - run the demo server sending email to MailHog (SMTP :1025)"
	@echo "services - run support services in the foreground (MailHog only); Ctrl+C stops them"
	@echo "services-sign - same as services, plus the Firmador digital-signature server"
	@echo "init_demo - reset the demo DB and load demo data + superuser"
	@echo "migrate - make and apply migrations for the demo"
	@echo "menu - (re)create demo data"
	@echo "notification_demo - load async_notification demo data"
	@echo "process-loop - simulate cron: run process_notifications every INTERVAL seconds (default 15)"
	@echo "loadstatic - download frontend libraries from CDN"
	@echo "basejs - regenerate base.js from widgets"
	@echo "assets - build the min.js/min.css bundles (pylp) and collectstatic for the demo"
	@echo "patch-pylp - patch the installed pylp for asyncio.wait compat"
	@echo "-- Quality --"
	@echo "test - run tests quickly with the default Python"
	@echo "test-selenium - Selenium E2E of the GUI, inside its own Xvfb display"
	@echo "test-selenium-run - the same, on the caller's display (no Xvfb)"
	@echo "coverage - unit suite under coverage + report + htmlcov/"
	@echo "coverage-all - the same, plus the selenium suite, combined"
	@echo "validate-mailhog - send every email feature to MailHog and validate reception"
	@echo "lint - check style (pycodestyle) and import placement (ruff)"
	@echo "lint-fix - auto-apply the mechanical style fixes with ruff"
	@echo "-- Build / release --"
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "docs - generate Sphinx HTML documentation, including API docs"
	@echo "release - package and upload a release"
	@echo "sdist - package"
	@echo "fuzzysdist - package"
	@echo "messages - load translations"
	@echo "trans - compile translations"

clean: clean-build clean-pyc

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info
	rm -fr djgentelella/static/vendors/*
	rm -fr djgentelella/static/djgentelella.vendors*
	rm -fr djgentelella/static/djgentelella.readonly.vendors*
	rm -fr djgentelella/static/djgentelella.flags.vendors*
	rm -fr djgentelella/static/djgentelella.maps.*

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +

# Two checkers, on purpose: pycodestyle owns style (options in setup.cfg, which
# it reads instead of pyproject.toml), ruff owns what pycodestyle cannot see --
# today PLC0415, imports that must live at the top of the module and not inside
# a function. Both trees in one call, so a failure in the first no longer hides
# the second.
lint:
	pycodestyle djgentelella demo
	ruff check djgentelella demo

# Apply the mechanical part of `make lint`: blank lines, trailing whitespace,
# end-of-file, then re-wrap what is still too long. Only long strings, comments
# and type comparisons are left for a human afterwards.
lint-fix:
	ruff check --select E,W --line-length 88 --preview --fix djgentelella demo
	ruff format --line-length 88 $$(pycodestyle djgentelella demo | cut -d: -f1 | sort -u)
	$(MAKE) lint

test:
	cd demo && python manage.py test --exclude-tag=selenium

# Every label the project has. Discovery starts in demo/, and the package tests
# live outside it, so each one has to be named explicitly or it is never run.
TEST_LABELS = demoapp djgentelella.tests djgentelella.blog.tests \
	djgentelella.async_notification

# The browser tests get a display of their own: `xvfb-run -a` picks the first
# free one, so the chromium they drive never steals focus from -- or paints
# over -- the session that launched them. Headless (the default) would not need
# an X server at all; the point of the Xvfb is that SELENIUM_HEADLESS=0 then
# works without touching the developer's screen, and that is the mode where
# Leaflet, the canvases and TinyMCE render as they do for a real user.
XVFB_ARGS ?= -screen 0 1600x1200x24
SELENIUM_HEADLESS ?= 1

test-selenium:
	xvfb-run -a -s "$(XVFB_ARGS)" $(MAKE) test-selenium-run

# Same suite without the Xvfb wrapper, for watching the browser on your own
# screen while debugging a failure.
test-selenium-run:
	cd demo && SELENIUM_HEADLESS=$(SELENIUM_HEADLESS) \
		python manage.py test $(or $(TEST),) --tag=selenium

# -- coverage ----------------------------------------------------------------
# Configuration lives in pyproject.toml ([tool.coverage.*]). Two things force
# the shape of these targets: manage.py inserts '..' relative to the *current
# directory*, so the tests only run from demo/; and coverage resolves both its
# rcfile and its data file relative to that directory too. Hence the absolute
# $(CURDIR) paths -- otherwise the unit pass and the selenium pass would write
# two unrelated data files inside demo/ and `combine` would have nothing to do.
COVERAGE_FILE ?= $(CURDIR)/.coverage
COV = COVERAGE_FILE=$(COVERAGE_FILE) coverage run --rcfile=$(CURDIR)/pyproject.toml

coverage: coverage-clean coverage-unit coverage-report

coverage-all: coverage-clean coverage-unit coverage-selenium coverage-report

coverage-unit:
	cd demo && $(COV) manage.py test $(TEST_LABELS) --exclude-tag=selenium

# Worth including: the live server runs in a thread of this same process, so
# coverage does see the views, serializers and template tags the browser hits.
coverage-selenium:
	xvfb-run -a -s "$(XVFB_ARGS)" $(MAKE) coverage-selenium-run

coverage-selenium-run:
	cd demo && SELENIUM_HEADLESS=$(SELENIUM_HEADLESS) \
		$(COV) manage.py test $(or $(TEST),) --tag=selenium

coverage-report:
	COVERAGE_FILE=$(COVERAGE_FILE) coverage combine
	COVERAGE_FILE=$(COVERAGE_FILE) coverage report
	COVERAGE_FILE=$(COVERAGE_FILE) coverage html -d htmlcov
	@echo "HTML report -> htmlcov/index.html"

coverage-clean:
	rm -rf htmlcov .coverage .coverage.*

docs:
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	#sphinx-build -b linkcheck ./docs/source docs/build/
	sphinx-build -b html ./docs/source docs/build/

# Refuses to build if the models drifted from the committed migrations: a
# release must not invent one, and `makemigrations` used to do exactly that
# silently, shipping a migration nobody reviewed.
check-migrations:
	cd demo && python manage.py makemigrations --check --dry-run

# Everything a release needs verified before the upload: metadata, README
# rendering on PyPI, and that the built package really carries the templates
# and static of every module.
check-dist:
	twine check dist/*
	python build_check.py

# Depends on sdist, not just check-dist: `twine upload dist/*` publishes whatever
# is on disk, so releasing without rebuilding would tag one version and upload
# whatever the previous build left behind.
release: sdist
	git tag -a "v$(version)" -m "Bump version $(version)"
	git push origin "v$(version)"
	twine upload dist/*

sdist: clean check-migrations patch-pylp
	cd demo && python manage.py loaddevstatic && python manage.py createbasejs
	python -m pylp
	cd djgentelella && django-admin compilemessages -l es
	python3 -m build
	$(MAKE) check-dist
	ls -l dist

fuzzysdist: patch-pylp
	cd demo && python manage.py makemigrations && python manage.py loaddevstatic && python manage.py createbasejs
	cd djgentelella && django-admin compilemessages -l es
	python -m pylp
	python3 -m build

messages:
	cd djgentelella && python ../demo/manage.py makemessages --all --no-location --no-obsolete && django-admin makemessages -d djangojs -l es  --ignore "static/*"   --ignore *.min.js --no-location --no-obsolete

trans:
	cd djgentelella && django-admin compilemessages --locale es

menu:
	cd demo && python manage.py createdemo

migrate:
	cd demo && python manage.py makemigrations && \
	python manage.py migrate

init_demo:
	cd demo && \
	rm -f db.sqlite3 && \
	python manage.py migrate && \
	python manage.py createdemo && \
	python manage.py demomenu && \
	python manage.py createsuperuser

PORT ?= 8000

run:
	cd demo && python manage.py runserver $(PORT)

run-mailhog:
	cd demo && EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend \
		EMAIL_HOST=localhost EMAIL_PORT=1025 \
		python manage.py runserver $(PORT)

services:
	./scripts/run_services.sh

services-sign:
	./scripts/run_services.sh --sign

notification_demo:
	cd demo && python manage.py create_notification_demo

INTERVAL ?= 15

process-loop:
	@echo "Simulating cron: process_notifications every $(INTERVAL)s (Ctrl+C to stop)"
	cd demo && EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend \
		EMAIL_HOST=localhost EMAIL_PORT=1025 \
		bash -c 'while true; do python manage.py process_notifications; sleep $(INTERVAL); done'

validate-mailhog:
	cd demo && python manage.py validate_mailhog

loadstatic:
	cd demo && python manage.py loaddevstatic

basejs:
	cd demo && python manage.py createbasejs

patch-pylp:
	pip install -q -r test_requirements.txt
	python scripts/patch_pylp.py

assets: patch-pylp
	python -m pylp && \
	cd demo && python manage.py collectstatic --noinput
