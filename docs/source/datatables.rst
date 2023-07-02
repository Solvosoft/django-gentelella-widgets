Datatables functionality
===========================

Events
-----------

**gtCreateDataTable events:**

It's call before return the request parameters, pass the parameter to be send, and require return of data

.. code:: javascript

        datatable_inits : {
          "events": {
            filter: function(data){
                            return data;
                    }
            }
        }


Columns render functions
------------------------------------

- yesnoprint:  Print fa-check-circle icon and text Yes o fa-times-circle and text No if No
- objShowBool:  Print fa-check-circle icon and text Yes o fa-times-circle and text No if No
- emptyprint:  Print ---- if object is none
- selectobjprint: Print an object using `display_name` attribute, also support pass the display_name  key to be used

  .. code:: javascript

        {data: "country", name: "country__name", title: "Country", type: "string", visible: true,
							render: selectobjprint({display_name: "name"}) },

- gt_print_list_object(display_name): Print object or List of objects using the display_name parameter as key
- showlink: Use data to create an A tag and print `More` text.
- downloadlink: Use data to create download link and print `Download` text.
- objshowlink: Use data to create an A tag, require the next structured on data returned from API

  .. code:: javascript

        {
            url: 'https://...',
            class: 'a class',
            display_name: 'text to display'
        }

- objnode: Use data to create an XX tag, require the next structured on data returned from API

  .. code:: javascript

        {
            url: 'https://...',
            class: 'a class',
            display_name: 'text to display',
            tagName: 'span',
            extraattr: ''
        }

Working with date and datetime fields
--------------------------------------------


When managing dates, it's necessary to take into account the date formats.

.. code:: javascript

    {data: "last_time", name: "last_time", title: gettext("Last Time"), type: "date",
    render: DataTable.render.datetime(), "dateformat":  document.datetime_format, visible: true},
    {data: "born_date", name: "born_date", title: gettext("Born date"), type: "date",
    render: DataTable.render.date(),  "dateformat":  document.date_format, visible: true},

In this case, it is assumed that the template provides the following formats in the document object using the template tags provided to determine the format configured in Django.

.. code:: javascript

    {% load timejs %}
    document.datetime_format="{% get_datetime_format %}";
    document.date_format="{% get_date_format %}";

Working with date and datetime fields on Server API
-------------------------------------------------------

Django Rest framework serializers for Date and Datetime fields has problems dealing with empty string "",
so when your date field is no required fail with validation error so we provide 2 serializers.

.. code:: javascript

    from djgentelella.serializers import GTDateField, GTDateTimeField

    class Myserializer(serializers.Serializer):
        creation_date = GTDateField()
        modification_datetime = GTDateTimeField()

