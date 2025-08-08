.PHONY: help clean clean-pyc clean-build list test  docs release sdist

djversion = $(python setup.py -V)
setupversion = $(awk -F "'" '{print $2}' djgentelella/__init__.py)

help:
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "lint - check style with flake8"
	@echo "test - run tests quickly with the default Python"
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
	cd demo && python manage.py test

docs:
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	sphinx-build -b linkcheck ./docs/source docs/build/
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
	cd djgentelella && python ../demo/manage.py makemessages --all --no-location --no-obsolete && django-admin makemessages -d djangojs -l es  --ignore *.min.js --no-location --no-obsolete

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
