.PHONY: help clean clean-pyc clean-build list test docs release sdist \
	lint test-selenium run run-mailhog mailhog mailhog-stop migrate menu init_demo \
	notification_demo validate-mailhog loadstatic basejs process-loop

djversion = $(python setup.py -V)
setupversion = $(awk -F "'" '{print $2}' djgentelella/__init__.py)

help:
	@echo "-- Run / demo --"
	@echo "run - run the demo dev server (PORT=8000 by default)"
	@echo "run-mailhog - run the demo server sending email to MailHog (SMTP :1025)"
	@echo "mailhog - start a MailHog container (SMTP :1025, web UI :8025)"
	@echo "mailhog-stop - stop the MailHog container"
	@echo "init_demo - reset the demo DB and load demo data + superuser"
	@echo "migrate - make and apply migrations for the demo"
	@echo "menu - (re)create demo data"
	@echo "notification_demo - load async_notification demo data"
	@echo "process-loop - simulate cron: run process_notifications every INTERVAL seconds (default 15)"
	@echo "loadstatic - download frontend libraries from CDN"
	@echo "basejs - regenerate base.js from widgets"
	@echo "-- Quality --"
	@echo "test - run tests quickly with the default Python"
	@echo "test-selenium - Selenium E2E of the GUI against MailHog (needs make mailhog)"
	@echo "validate-mailhog - send every email feature to MailHog and validate reception"
	@echo "lint - check style with pycodestyle (max-line-length=88)"
	@echo "-- Build / release --"
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "docs - generate Sphinx HTML documentation, including API docs"
	@echo "release - package and upload a release"
	@echo "sdist - package"
	@echo "fuzzysdist - package"
	@echo "messages - load translations"
	@echo "trans - compile translations"
	@echo "start_sign - start sign server"

clean: clean-build clean-pyc

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info
	rm -fr djgentelella/static/vendors/*
	rm -fr djgentelella/static/djgentelella.vendors*

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +

lint:
	pycodestyle --max-line-length=88 djgentelella --exclude=djgentelella/management/commands/loaddevstatic.py
	pycodestyle --max-line-length=88 demo --exclude=demo/demoapp/gtstorymap.py

test:
	cd demo && python manage.py test --exclude-tag=selenium

test-selenium:
	cd demo && python manage.py test $(or $(TEST),) --tag=selenium

docs:
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	#sphinx-build -b linkcheck ./docs/source docs/build/
	sphinx-build -b html ./docs/source docs/build/

release:
	git tag -a "v`python djgentelella/__init__.py`" -m "Bump version `python djgentelella/__init__.py`"
	git push origin "v`python djgentelella/__init__.py`"
	twine upload -s dist/*

sdist: clean
	cd demo && python manage.py makemigrations && python manage.py loaddevstatic && python manage.py createbasejs
	python -m pylp
	cd djgentelella && django-admin compilemessages -l es
	python3 -m build
	ls -l dist

fuzzysdist:
	cd demo && python manage.py makemigrations && python manage.py loaddevstatic && python manage.py createbasejs
	cd djgentelella && django-admin compilemessages -l es
	python -m pylp
	python3 -m build

messages:
	cd djgentelella && python ../demo/manage.py makemessages --all --no-location --no-obsolete && django-admin makemessages -d djangojs -l es  --ignore "static/*"   --ignore *.min.js --no-location --no-obsolete

trans:
	cd djgentelella && django-admin compilemessages --locale es

docker_sign:
	docker run -d --rm  --name firmadorserver -p 9001:9999 -d firmadorlibreserver

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
MAILHOG_NAME ?= djgentelella_mailhog

run:
	cd demo && python manage.py runserver $(PORT)

run-mailhog:
	cd demo && EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend \
		EMAIL_HOST=localhost EMAIL_PORT=1025 \
		python manage.py runserver $(PORT)

mailhog:
	docker run -d --rm --name $(MAILHOG_NAME) \
		-p 8025:8025 -p 1025:1025 mailhog/mailhog
	@echo "MailHog up -> SMTP localhost:1025, web UI http://localhost:8025"

mailhog-stop:
	docker stop $(MAILHOG_NAME)

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
