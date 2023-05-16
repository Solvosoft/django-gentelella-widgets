======================
Notifications APIView
======================


Using the API
--------------

The view ``notification_list_view`` (login required) shows all the notifications filtered for the logged in user.
This view takes the information from the API through the class ``NotificationViewSet`` in */djgentelella/notification/base.py*.

The viewset uses a ``serializer_class`` defined in */djgentelella/notification/serializer.py* as ``NotificationDatatableSerializer``
where the serialized notifications are taken as the data attribute. The ``NotificationSerializer`` is based on
``Notification`` model, taking the fields: ``id``, ``description``, ``link``, ``message_type``, ``state``, ``creation_date`` and ``user``;
using ``UserSerializer`` (taking fields id and username) for user and ``DateTimeField`` to give the proper format to the notification's creation date.
The ``pagination_class`` is set as ``LimitOffsetPagination``.

The items shown in view set are ordered with the below priority:

#. Creation date
#. Message type
#. Description
#. Link
#. State

Because of the information contained in every notification, the fields destined as search field are ``message_type``, ``description`` and ``state``.

Using the ``NotificationFilterSet`` as the ``filterset_class``, the ``NotificationViewSet`` defines the filtering functionality in the datatable
through the name of the columns (directly related to how it is named in the template inside de ``createDataTable`` function).

The list function filters the queryset to be shown matching the user on each notification to the current
authenticated user, then a response is sent to */gentelella/menu/notification_list.html* containing
the group of notifications as ``'data'``, the total amount of notifications and the filtered ones by the names
``'recordsTotal'`` and ``'recordsFiltered'``, respectively.

Using the datatables
--------------------
At the end of */gentelella/menu/notification_list.html*, the script section calls the ``createDataTable`` function
using the id ``'notificationdatatable'`` and setting each column with the correspondent header name and row data. It's necessary to
use a render parameter in some columns to give it the proper format, e.g. the ``message_type`` is a string, even so, it's shown
as a colored circle in the view. Also the link of each notification has a text with a hyperlink to the notification. The
'State' column use render just to capitalize the first letter of the string. Also, within that script, there is a function
used to update the ``document.dom`` of the datatable, specifically to give it a proper looking using some bootstrap classes.
