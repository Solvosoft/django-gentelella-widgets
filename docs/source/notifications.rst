======================
Notifications feature
======================

How it works ??

The custom command createdemo, create in the sidebar two buttons to create notifications the second button can sent emails

.. code:: python

     noti=MenuItem.objects.create(
            parent = item,
            title = 'Create notification',
            url_name ='/create/notification',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = False,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = 'fa fa-power-off',
            only_icon = False
        )
        MenuItem.objects.create(
            parent = item,
            title = 'Create notification email',
            url_name ='/create/notification?email=1',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = False,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = 'fa fa-power-off',
            only_icon = False
        )

Then from the djgentelella.notication the create_notification subrutine must be imported.
Also the user must be login in order to use this feature, as notification require a user
to be registered, and also for the second case in which we wish to sent a email.

.. code:: python

   from djgentelella.notification import create_notification

   @login_required
   def create_notification_view(request):
       email = request.GET.get('email', '')
       if email:
           create_notification("This es an example of notification system with email", request.user,
               'success', link='notifications',
                link_prop={'args': [], 'kwargs': {'pk': 2}},
                           request=request, send_email=True)
       else:
           create_notification("This es an example of notification system", request.user,
                   'success', link='notifications',
                    link_prop={'args': [], 'kwargs': {'pk': 2}}, request=request)

       messages.success(request, 'A notification was created, check the widget')

       return redirect("/")

The Notification model comes from djgentelella app model.