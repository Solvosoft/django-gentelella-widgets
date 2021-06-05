===============
Permission Management
===============

This feature allow as to manage permissions per view, so we can asociate an 
specific url name with an specific permission codename and permission category.

---------------------
 Live Demo 
---------------------

.. image:: ./_static/01-permissionmanagement.gif


You can use two main approches to achieve this:
   - Use `get_or_create_permission_context`.
   - Create the permission manually.

--------------------------
Define programatically.
--------------------------

1. You must create a `pre_head` block as the following example in your template:
 
.. code-block:: bash

   {% block pre_head %}
      {% get_or_create_permission_context 'pgroup-list' 'demoapp' 'view_peoplegroup' 'List groups' 'Group' %}
      {% define_urlname_action 'pgroup-list'%}
   {% endblock%}

The parameters in here are the following:
   - `urlname`: Can be a list serparated by commas
   - `appname`: This is 78 name of the app asocciated with the permission.
   - `codename`: Can be a list of django codenames that are associated with the urlnames.
   - `humanname` Is a list names related to the code names this names will be display to the user.
   - `category`: Is the name that will join differents permissions together.

Make sure that `urlname`, `codename` and `humanname` has the same number of elements.

It is possible to define also:

.. code-block:: bash

   {% block pre_head %}
      {% get_or_create_permission_context 'pgroup-list,pgroup-edit' 'demoapp' 'view_peoplegroup,change_peoplegroup' 'List groups,Change group' 'Group' %}
      {% define_urlname_action 'pgroup-list'%}
   {% endblock%}

So we can define a list of permissions in the template tag.


If you want to keep your code clearly:

.. code-block:: bash

   {% block pre_head %}
      {% get_or_create_permission_context 'pgroup-list' 'demoapp' 'view_peoplegroup' 'List groups' 'Group' %}
      {% get_or_create_permission_context 'pgroup-edit' 'demoapp' 'change_peoplegroup' 'Change group' 'Group' %}
      {% define_urlname_action 'pgroup-list'%}
   {% endblock%}


The default behavior of the djgentellela is that if you are superadmin will display de button 
to manage the permissions similar to the Live Demo.

If you want to change the permissions you can override the following partial `gentelella/app/top_navigation.html` and 
also in `gentelella/base.html`

-------------------------------
Define permissions manually
-------------------------------

To do this you have to go to the admin panel and go to gentellella app:

.. image:: ./_static/02-permissionmanagement-admin.png

The we can create a new permission as the following example:

.. image:: ./_static/03-permissionmanagement-add.png

And in your view because you created the permission manually just need to create in your template the following:

.. code-block:: bash

   {% block pre_head %}
      {% define_urlname_action 'group-add' %}
   {% endblock%}

It's really important that you define all the context in the `pre_head` block otherwise it will not work.