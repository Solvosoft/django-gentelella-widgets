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

clean: clean-build clean-pyc

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info
	rm -fr djgentelella/static/vendors/*

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
	sphinx-build -b linkcheck ./docs/source _build/
	sphinx-build -b html ./docs/source _build/


release: sdist
	git tag -a "v`python setup.py --version`" -m "Bump version `python setup.py --version`"
	git push origin "v`python setup.py --version`"
	twine upload -s dist/*

sdist: clean
	cd demo && python manage.py makemigrations && python manage.py loaddevstatic && python manage.py createbasejs
	cd djgentelella && django-admin compilemessages -l es
	python3 -m build
	ls -l dist

