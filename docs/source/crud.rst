===============
CRUDView Usage
===============


Using CRUDView
----------------

CRUDView is a generic way to provide create, list, detail, update, delete views
in one class, you can inherit for it and manage login_required, model perms,
pagination, update and add forms

How to use:

In your views file create a class inherit for CRUDView

.. code:: python

    from testapp.models import Customer
    from djgentelella.cruds.base import CRUDView
    class Myclass(CRUDView):
        model = Customer

In urls.py

.. code:: python

    myview = Myclass()
    urlpatterns = [
        url('path', include(myview.get_urls()))  # also support
                                                 # namespace
    ]

If you want to filter views add views_available list

.. code:: python

    class Myclass(CRUDView):
        model = Customer
        views_available=['create', 'list', 'delete', 'update', 'detail']

Permissions
------------

The default behavior is check_login = True and check_perms=True but you can
turn off with

.. code:: python

    from testapp.models import Customer
    from cruds_adminlte.crud import CRUDView

    class Myclass(CRUDView):
        model = Customer
        check_login = False
        check_perms = False

You also can defined extra perms in two ways as django perm string or like a function


.. code:: python

    def myperm_system(user, view):
       # user is django user
       # view is one of this 'list', 'add', 'update', 'detail'
       return True or False

    class Myclass(CRUDView):
        model = Customer
        perms = { 'create': ['applabel.mycustom_perm'],
                  'list': [],
                  'delete': [myperm_system],
                  'update': [],
                  'detail': []
                }

If check_perms = True we will add default django model perms
(<applabel>.[add|change|delete|view]_<model>) ej. mytestapp.add_mymodel

Searching
------------

As django admin does, **search_fields** are available, and you can filter using
double underscore (__) to search across the objects.

**split_space_search** split search text in parts using the string provided,
this can be usefull to have better results but have impact in search
performance, if split_space_search is True then ' ' is used

.. code:: python

    class Myclass(CRUDView):
        model = Customer
        search_fields = ['description__icontains']
        split_space_search = ' ' # default False

.. note:: 'icontains' is not set by default as django admin does, so you need
          to set if not equal search is wanted

.. image:: https://raw.githubusercontent.com/oscarmlage/django-cruds-adminlte/master/docs/images/cruds-search.png
    :target: https://raw.githubusercontent.com/oscarmlage/django-cruds-adminlte/master/docs/images/cruds-search.png

Filter content
---------------

.. warning::
    Code preserve filter it's a complex task, and filter content with high
    grade of liberty is hard to do, so this is a experimental version.

Use **list_filter** as list of model attributes or FormFilter objects like:

.. code:: python

    class Myclass(CRUDView):
        model = Invoice
        list_filter = ['invoice_number', 'sent', 'paid']

Filter method is based on forms and filter query set, so we use different
approach compared with django admin

**FormFilter** is a special class used for filter content based on form.

.. code:: python

    from djgentelella.cruds.filter import FormFilter
    class LineForm(forms.Form):
        line = forms.ModelMultipleChoiceField(queryset=Line.objects.all())

    class LineFilter(FormFilter):
        form = LineForm

    class Myclass(CRUDView):
        model = Invoice
        list_filter = ['sent', 'paid', LineFilter]

Magic.., not, just and good example of how to do a multiple value search based
end a reverse foreignkey.

FormFilter has this public method:

* **render():** return a form or your own html, has an instance of form in
  self.form_instance, and also has self.request.
* **get_filter(queryset):** filter your content here
* **get_params(exclude):** clean the get parameters


Pagination
---------------

Pagination is supported for list view using **paginate_by** and
**paginate_template**, the default pagination value is:

* paginate_by = 10
* paginate_template = 'gentelella/cruds/prev_next.html'
* paginate_position = 'Bottom'

For example paginate custumers using enumeration paginate

.. code:: python

    class Myclass(CRUDView):
        model = Customer
        paginate_by = 5
        paginate_template = 'gentelella/cruds/enumeration.html'
        paginate_position = 'Both'

The **paginate_position** options are *Bottom*, *Both*, *Up*

Overwrite forms
-------------------

You can also overwrite add and update forms

.. code:: python

    class Myclass(CRUDView):
        model = Customer
        add_form = MyFormClass
        update_form = MyFormClass

.. warning::
    Forms are decorated after creation to provice better widgets for basic form fields

Overwrite templates
----------------------

And of course overwrite base template name

.. code:: python

    class Myclass(CRUDView):
        model = Customer
        template_name_base = "mybase"

Remember basename is generated like app_label/modelname if template_name_base
is set as None add 'cruds' by default so template loader search this structure

.. code:: bash

    basename + '/create.html'
    basename + '/detail.html'
    basename + '/update.html'
    basename + '/list.html'
    basename + '/delete.html'

.. Note::
    Also import <applabel>/<model>/<basename>/<view type>.html


Using namespace
-----------------

There is no way to create 2 CRUDView to the same model, because urls could be
crash, so namespace come to help with this, `namespace` are part of django urls
system and allows to have same urls with diferent context, so you can use this
to add different behaivior to a model, also different urls.

In views

.. code:: python

    from testapp.models import Customer
    from djgentelella.cruds.base import CRUDView
    class Myclass(CRUDView):
        model = Customer
        namespace = "mynamespace"

In urls.py

.. code:: python

    myview = Myclass()
    urlpatterns = [
        url('path', include(myview.get_urls(),
                            namespace="mynamespace"))
    ]

Namespace in views and urls needs to match, or url match problem are raise.

Related fields
----------------

A common scenario is that you have a model with a foreignkey to other model
that is the main of your view so you want to pass the main model as parameter
to a crud views to filter and create using it as main reference, and always
save the foreignkey with the main model object.

For example
In models

.. code:: python

    class Author(models.Model):
        name=models.CharField(max_length=150)
    class Book(models.Model):
        author = models.ForeignKey(Author):
        name=models.CharField(max_length=150)

In views

.. code:: python

    from cruds_adminlte.crud import CRUDView
    class Myclass(CRUDView):
        model = Book
        related_fields = ['autor']

So with this you now have management of author's book.

.. warning::
    we provide all internal references but you need to create the
    first author to book list|create|update|detail|delete reference.


Decorators
-------------------

CRUDViews use a generic Django views and provide some utilities to manage
decorator. As django documentation say you can use decorator in urls when you
call as_view method in generic views like.

In urls.py

.. code:: python

    urlpatterns = [
        url('list', login_required(ListView.as_view()) )
    ]

CRUDViews take advantage of this and create this methods

- decorator_create(self, viewclass)
- decorator_detail(self, viewclass)
- decorator_list(self, viewclass)
- decorator_update(self, viewclass)
- decorator_delete(self, viewclass)

So you can overwrite it and put your own decorator.  Be warried about
login_required decorator, because when check_login is set we used this method
to insert login_required decorator.

How to overwrite:

In views

.. code:: python

    from testapp.models import Customer
    from djgentelella.cruds.base import CRUDView
    class Myclass(CRUDView):
        model = Customer
        def decorator_list(self, viewclass):
            viewclass = super(Myclass, self).decorator_list(viewclass) # help with
                                                                       # login_required
            return mydecorator(viewclass)


Overwrite views
-------------------

Overwrite views are easy because we are using django generic views, but you
need to have some worry.

If you don't need to overwrite this functions

- get_template_names
- get_context_data
- dispatch
- paginate_by attr in list view

then you can overwrite and return your own class

- get_create_view_class
- get_update_view_class
- get_detail_view_class
- get_list_view_class
- get_delete_view_class

but if you need to overwrite some of the above functions you need to overwrite

- get_create_view
- get_update_view
- get_detail_view
- get_list_view
- get_delete_view

Like

.. code:: python

    from testapp.models import Customer
    from djgentelella.cruds.base import CRUDView
    class Myclass(CRUDView):
        model = Customer
        def get_list_view(self):
            ListViewClass = super(Myclass, self).get_list_view()
            class MyListView(ListViewClass):
                def get_context_data(self):
                    context = super(MyListView, self).get_context_data()
                    return context
            return MyListView

.. warning::
    It's really important that you use *super(MyListView,
    self).get_context_data()* instead of ListView.get_context_data() because we
    insert some extra context there.

===================
UserCRUDView Usage
===================

A usefull utility class is provided named as UserCRUDView, and works link
CRUDView but include user management, but require than base model has user
attribute.

In Create and Update view save the model adding current user as user attribute.
In List View filter objects using current user.

In models

.. code:: python

    # from django.contrib.auth.models import User
    from django.contrib.auth import get_user_model
    User = get_user_model()
    from django.db import models
    class Customer(models.Model):
        user = models.ForeignKey(User)
        ...

In views

.. code:: python

    from testapp.models import Customer
    from djgentelella.cruds.base import CRUDView
    class Myclass(UserCRUDView):
        model = Customer

======================
CRUDMixin Usage
======================

CRUDMixin is a mixin-like class that all the views inherit from. It provides a
convenient way of customizing your views, requiring of no additional changes.
You can access that class when calling the functions "crud_for_app" or
"crud_for_models", passing the reference to your custom CRUDMixin object as a
new parameter to any of these functions.

The following example uses the class "MyMixin" to customize the object called
"context_data" for all the views. This way, all the templates will have a new
object called "cars" available.

.. code:: python

    class MyMixin(CRUDMixin):
        def get_context_data(self, *args, **kwargs):
            context = super(Mixin, self).get_context_data(*args, **kwargs)
            context['cars'] = MyModel.objects.all()
            return context

    urlpatterns += crud_for_app('myapp', login_required=True, mixin=MyMixin)

.. warning::
    The class "MyMixin" needs to inherit from "CRUDMixin"; otherwise an
    exception is raised.
