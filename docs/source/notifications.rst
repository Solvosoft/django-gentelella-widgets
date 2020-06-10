======================
Notifications Menu
======================

How it works ??

The custom command createdemo, create in the sidebar two buttons to create notifications the second button can sent emails.

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

.. image:: https://user-images.githubusercontent.com/20632410/84221770-3a1b3f00-aa93-11ea-9546-2c3e9d337d65.png

Also create a widget in the top navbar right side corner in wich we can access a modal with notifications when we hit the email icon.

.. image:: https://user-images.githubusercontent.com/20632410/84221507-9f226500-aa92-11ea-977f-f762083d5d38.png

with the following code

.. code:: python

   item = MenuItem.objects.create(
       parent = None,
       title = 'top_navigation',
       url_name ='djgentelella.notification.widgets.NotificationMenu',
       category = 'main',
       is_reversed = False,
       reversed_kwargs = None,
       reversed_args = reverse('notifications'),
       is_widget = True,
       icon = 'fa fa-envelope',
       only_icon = False
   )

Then to implement this feature we must import from the djgentelella.notication the create_notification subrutine.
In the view we must require the user as his account and email are required to create notifications and send emails.

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