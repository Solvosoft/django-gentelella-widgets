======================
Permission Management
======================

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
 
.. code-block:: python

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

.. code-block:: python

   {% block pre_head %}
      {% get_or_create_permission_context 'pgroup-list,pgroup-edit' 'demoapp' 'view_peoplegroup,change_peoplegroup' 'List groups,Change group' 'Group' %}
      {% define_urlname_action 'pgroup-list'%}
   {% endblock%}

So we can define a list of permissions in the template tag.


If you want to keep your code clearly:

.. code-block:: python

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

.. code-block:: python

   {% block pre_head %}
      {% define_urlname_action 'group-add' %}
   {% endblock%}

It's really important that you define all the context in the `pre_head` block otherwise it will not work.

-----------------------------------------
Use different model that User and Group
-----------------------------------------

To use different User model you have to add to your settings.py the following:

.. code-block:: python
   
   GT_USER_MODEL = 'demoapp.Employee'

And your custom model need to implement the following function:

.. code-block:: python

   class Employee(models.Model):
      user = models.ForeignKey(User, on_delete=models.CASCADE)
      username = models.CharField(max_length=100)

      #username also can be a @property to user.username.

      @property
      def gt_get_permission(self):
         return self.user.user_permissions

      def __str__(self):
         return self.username

You need a `gt_get_permission` method that return the relative relation to permissions model.
Make sure that you have the `username` field that can be a `CharField` or a `@property` in this way
djgentellela will display all the information properly.

To use different Group model you have to add to your settings.py the following:

.. code-block:: python
   
   GT_GROUP_MODEL = 'demoapp.Employee'

And your custom model has to be like the following:

.. code-block:: python

   class PermissionsGroup(models.Model):
      name = models.CharField(max_length=150)
      department = models.ForeignKey(Department, on_delete=models.CASCADE)
      permission = models.ManyToManyField(PermissionDescription, blank=True)
      users = models.ManyToManyField(User, blank=True)

      @property
      def gt_get_permission(self):
         return self.permission

Make suere you have the `gt_get_permission` and the `name` field that also of course can be a `@property`.

-------------------------------
Top Navegation
-------------------------------

For get the key on the top navegation you need write the next code in the templates menu presentation/temmplates/gentelella/app/
organization_add.html.

.. code-block:: python

    {% endif %}
      <ul class="nav navbar-nav navbar-right">
      {%get_urlname_action as urlnameaction %}
      {%validate_context urlnameaction as context %}
      {%if urlnameaction and contex %}
      <li><a class="btn" id="btn_perms" title="Add Permission" data-toggles="modal" data-target="#permission_modal" data-permeters={% get_page_name urlnameacation %}"data urlname="{{urlnameactions}}" style"..."><i class"fa fa-key fa-zx" "aria-hidden="true"></i></a></li>
    {% endif %}


it´s really important define the permission for view

The additional Permission that you add will go to the premission list URLNAME_PERMISSION

and we calle it with the next command.

.. code-block::python
    class command(BaseCommand):
        help = ' Load permission category '

    def get_permission(self. app_codename):
        perm = None
        val = app_codename.slipt('.')
    if lenv(val) == 2:
        perm = Permission.objects.filter(
        codename==val[1]
        content_type__app_label=val[0]
    return perm


    def load_urlname_permissions(self):
    for url_name, item_list in URLNAME_PERMISSION.items():

    for obj in item_list:
    perm = self.get_permission(obj['permission'])

    if perm:
        permcat = PermissionCategoryManagement.objects.filter(name=obj['name']. category=obj['category'],
									    permission=perm.firts(), url_name=url:name)

    if not permcat.exists():
    new.permcat = PermissionCategoryManagement(
    (name=obj['name']. category=obj['category'],permission=perm.firts(), url_name=url:name)
    new_permcat.save()
    else:
        print("'"+obj['name']+ "'already exists.")
    else:
        print("'"+obj['permisison']+ "'doesn´t exists.")

    def handle(self,*args,**options):
        PermissionCategoryManagement.objects.all().delete()
        self.load_urlname_permission()



   Let's see what we have now
   The command call the list URLNAME_PERMISSON get method permisson from codename y el content_type_app_label
   if the permission doesn't exist will print us "doesn't exist"
   but once permission is obtained is created and it is filtered to know if it already exists and will be creating with the name,category,permission, urlname that we already write

   then a delete it's done and saved.
   we have the example of how they are loaded view by view

-------------------------------

Model of user and Group

-------------------------------

    we have role user and grup

    each grup has users in each grup we maybe have 3 o 4 members and we can attribute the permissions to each group so that each member has them

    Note: not all users will be able to edit permissions only users with respective permissions


.. code-block:: python

    class PmBAse

	    def get_permission_list(self):
		  categories = {}
          q = self-form.cleaned_data['urlname']
	    permission_list = PermissionCategoryManagement.objects.filter(url_name__in=q.slipt(',')). \
	    values('category','permission','name')

	   for perm in permission_list:
	      if perm['category'] not in categories:
		  categories[perm['category']] =[]

	        categories[perm['category']].append{'id': perm['permission'],
                                                 'name': perm['name'}})

		  return categories





.. code-block:: python

	class PmUser(PmBase):

	    def__init__(self,request,form):
	   	 self.form=form
	    	 self.request = request

         def get_django_permission(self,pk):
	       perms = []
		 q = self.form_cleaned_data{'urlname'}
		 User = User.objects.get(pk=pk)
		 if hasattr(user, 'gt_get_permission'):
		    permission = user.gt_get_permission.all()
		 else:
			permission = user.permission.all()
		   permisson_list = PemissionCategoryManagement.objects.filter(url_name__in=q.slip(','))
		   for perm in permission_list.filter(permission__in=permission).values(
			       'permission', 'permission_name', 'permission_codename'):
				 perms.append({'id': perm['permission'], 'name' perm['permission_name'],
					          'codename': perm['permission_codename]})


		return perms

        def update_permission(self):
            user = self.form.cleaned_data{'user'}
		old_user_permission = set(map(lamba x: x['id'], self.get_django_permission(user.pk)))
	      set_permission_list = set(self.form.cleaned_data['permissions'].values_list('pk',flat=True))

		remove_permission = old_user_permission - set_permission_list
		add_permission = set_permission_list - old_user_permission

		if hasattr(user,'gt_get_permission'):
		    user.gt_get_permisson.remove(*remove_permission)
		else:
		     user.user_permission.remove(*remove_permission)

		if hasattr(user,'gt_get_permission'):
		    user.gt_get_permisson.add(*add_permission)
		else:
		     user.user_permission.add(*add_permission)


.. code-block:: python
   class PmGroup(PmBase):

	   def__init__(self,request,form):
	   	 self.form=form
	    	 self.request = request

         def get_django_permission(self,pk):
	       perms = []
		 q = self.form_cleaned_data{'urlname'}
		 group = Group.objects.get(pk=pk)
		 if hasattr(user, 'gt_get_permission'):
		    permission = group.gt_get_permission.all()
		 else:
			permission = group.permission.all()
		   permisson_list = PemissionCategoryManagement.objects.filter(url_name__in=q.slip(','))
		   for perm in permission_list.filter(permission__in=permission).values(
			       'permission', 'permission_name', 'permission_codename'):
				 perms.append({'id': perm['permission'], 'name' perm['permission_name'],
					          'codename': perm['permission_codename]})


		 return perms

        def update_permission(self):
            group = self.form.cleaned_data{'user'}
		    old_group_permission = set(map(lamba x: x['id'], self.get_django_permission(user.pk)))
	        set_permission_list = set(self.form.cleaned_data['permissions'].values_list('pk',flat=True))

		    remove_permission = old_group_permission - set_permission_list
		    add_permission = set_permission_list - old_user_permission

		 if hasattr(user,'gt_get_permission'):
		    group.gt_get_permisson.remove(*remove_permission)
		 else:
		     user.group_permission.remove(*remove_permission)

		 if hasattr(group,'gt_get_permission'):
		    group.gt_get_permisson.add(*add_permission)
		 else:
		     group.group_permission.add(*add_permission)


	we have a Base that is used to get the list of permission, for user and each group
	we get from the Base the urlname and all the permission associated with the ulrname are filtered
	you get the values that are category,permission and name


	get_django-permission ask to 'get_get_permission' for know if already exist because could be modified
	the permisison_list and PermisisonCategoryManagement they will be filtered for the urlname

	The permission_list and CategoryManagement they will be filtered by the urlname that we are defining

	Then we have a method named def update_pemission(self):
	and it is to update the permissions of the user and the group
	we have the user and group with a form, the recent permission and the permission it going to set.

.. code-block::python
     Class ObjManager:

       @staticmethod

     def get_class(request,form):
          if form.cleaned_data['option'] == '1':
	           return PMUser(request, form)
              elif form.cleaned_data['option'] == '2'
	           return PMGroup(request, form)


	we use a class named ObjManager to ask if is a user or a gruop and hide the select of permisison



































Happy coding.
