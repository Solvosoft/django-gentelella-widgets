===============
This is the django-gentelella demo WEB site
===============


How to execute django-gentelella demo ??
----------------

In order to execute the demo WEB site in which django-gentelella is implemented you must follow these steps:

from the terminal after cloned the repository

1. you must create an environment and active it, as follows
.. code-block:: bash

   $ virtualenv env -p python3.8
   $ source env/bin/activate

2. the second step is to install the requirements
.. code-block:: bash

   $ pip install -r requirements

3. then in django-gentelella-widgets/demo directory you must execute django migrate command
.. code-block:: bash

   $ python manage.py migrate

4. load the side bar menu with this custom command
.. code-block:: bash

   $ python manage.py createdemo

5. after that install requests library and execute django-gentelella custom command to download and set assets
.. code-block:: bash

   $ pip install requests
   $ python manage.py loaddevstatic

6. the project at this point is ready so, launch the server with
.. code-block:: bash

   $ python manage.py runserver
