#!/usr/bin/bash

rm -rf djgentelella/static/vendors
mkdir djgentelella/static/vendors
cd demo
python manage.py createbasejs
python manage.py loaddevstatic
cd ..
python setup.py sdist
