===============
Demo web site
===============

In order to execute the demo WEB site in which django-gentelella is implemented you must follow these steps:

From the terminal after cloned the repository.

1. You must create an environment and active it, as follows:

.. code-block:: bash

   $ virtualenv env -p python3.8
   $ source env/bin/activate

2. The second step is to install the requirements:

.. code-block:: bash

   $ pip install -r requirements.txt

3. Then in django-gentelella-widgets/demo directory you must execute django migrate command:

.. code-block:: bash

   $ python manage.py migrate

4. Load the side bar menu with this custom command:

.. code-block:: bash

   $ python manage.py createdemo

5. After that install requests library and execute django-gentelella custom command to download and set the assets with:

.. code-block:: bash

   $ pip install requests
   $ python manage.py loaddevstatic

6. At this point the project is ready so, launch the server with:

.. code-block:: bash

   $ python manage.py runserver
