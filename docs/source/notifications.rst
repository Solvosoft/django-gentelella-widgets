======================
Notifications APIView
======================


Using the API
--------------

The view notification_datatable_view (login required) shows all the notifications filtered for the logged in user.
This view takes the information from the API through the class NotificationViewSet in /demoapp/datatables/api.py.

The viewset uses a serializer_class defined in /demoapp/datatables/serializer.py as NotificationDatatableSerializer
where the serialized notifications are taken as the data attribute. The NotificationSerializer is based on
Notification model, taking all fields of model, using UserSerializer (taking fields id and username) for user and
DateTimeField to give the proper format to the notification's creation date. The pagination_class is set as LimitOffsetPagination

The items shown in view set are ordered with the below priority:

#. Creation date
#. Message type
#. Description
#. Link
#. State

Because of the information contained in every notification, the fields destined as search field are message_type and state.

The list function filters the queryset to be shown matching the user on each notification to the current
authenticated user, then a response is sent to /gentelella/datatables/notification_datatables.html containing
the group of notifications as 'data', the total amount of notifications and the filtered ones by the names
'recordsTotal' and 'recordsFiltered', respectively.

Using the datatables
--------------------
At the end of /gentelella/datatables/notification_datatables.html, the script section calls the createDataTable function
using the id 'datatableelement' and setting each column with the correspondent header name and row data. It's necessary to
use a render parameter in some columns to give it the proper format, e.g. the message_type is a string even so, it's shown
as a colored circle in the view. Also the link of each notification has a text with a hyperlink to the notification. The
'state' column use render just to capitalize the first letter of the string.
