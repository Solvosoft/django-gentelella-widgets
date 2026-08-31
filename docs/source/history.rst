History functionality
===========================

Configuration
------------------

To enable history tracking, you must configure the models that will be monitored.
This is done in your ``settings.py`` file by adding them as ``app.model`` references:

.. code:: python

    # history
    GT_HISTORY_ALLOWED_MODELS = [
        "djgentelella.trash",  # always add trash when you use history
        "demoapp.customer",
        # add more models here for history
    ]

History Filter Form
-------------------------

A filter form can be created to allow selecting categories when viewing history:

.. code:: python

    from django import forms
    from djgentelella.forms.forms import GTForm
    from djgentelella.widgets import core as genwidgets
    from django.utils.translation import gettext_lazy as _

    class HistoryFilterForm(GTForm, forms.Form):
        category = forms.ChoiceField(
            choices=[
                ("--------", _("All")),
                ("demoapp.customer", _("Customer")),
                ("djgentelella.trash", _("Trash")),
                # add more categories here
            ],
            widget=genwidgets.Select,
            label=_("Category"),
        )

History Template
-----------------------

The template defines how the history page will be displayed.
In this example, we extend the base layout and render the history table:

.. code:: html+django

    {% extends 'gentelella/base.html' %}
    {% load static i18n %}

    {# page title #}
    {% block title %} {% trans 'History' %} {% endblock %}

    {# page content #}
    {% block content %}
        <h1 class="text-center"> {% trans 'History Example' %} </h1>
        <hr>
        <div class="card mt-2">
            <div class="card-body">
                <div class="card-title titles">
                    <h2 class="text-center"> {% trans 'History' %} </h2>
                </div>

                {# table history #}
                <div class="row mt-3 ">
                    <div class="col-6">
                        {{ form }}
                    </div>
                    <div class="col-12">
                        <table class="table table-hover table-striped w-100 table-responsive" id="table-history">
                        </table>
                    </div>
                </div>
            </div>
        </div>
    {% endblock %}

JavaScript Initialization
---------------------------------

Finally, we define the JavaScript logic to configure the datatable, filters, and actions:

.. code:: javascript

    const choices_actions = [
        [1, gettext("Addiction")],
        [2, gettext("Modification")],
        [3, gettext("Deletion")],
        [4, gettext("Hard deletion")],
        [5, gettext("Restoration")]
    ]

    const selects2_urls = {
        users: "{% url 'users-list' %}",
    }

    const object_urls = {
        list_url: "{% url 'api-history-list'  %}",
    }

    const datatable_inits = {
        columns: [
            {
                data: "action_time", name: "action_time", title: gettext("Date"), type: "date",
                "dateformat": document.datetime_format, visible: true
            },
            {
                data: "user", name: "user", title: gettext("User"), url: selects2_urls['users'],
                type: "select2", visible: true
            },
            {data: "change_message", name: "change_message", title: gettext("Detail"), type: "string", visible: true},
            {data: "object_repr", name: "object_repr", title: gettext("Information"), type: "string", visible: true},
            {
                data: "action_flag", name: "action_flag", title: gettext('Action'), type: "select",
                choices: choices_actions, visible: true
            },
            {data: "actions", name: "actions", title: gettext("Actions"), type: "string", visible: false}
        ],
        addfilter: true,
        events: {
            'filter': function (data) {
                data['contenttype'] = document.getElementById("id_category").value;
                return data
            }
        }
    }

    const modalids = {}

    const actions = {
        table_actions: [],
        object_actions: [],
        title: gettext('Actions'),
        className: "no-export-col"
    }

    const icons = {
        clear: '<i class="fa fa-eraser" aria-hidden="true"></i>',
    }

    const objconfig = {
        datatable_element: "#table-history",
        modal_ids: modalids,
        actions: actions,
        datatable_inits: datatable_inits,
        add_filter: true,
        relation_render: {'field_autocomplete': 'text'},
        delete_display: '',
        create: "btn-success",
        icons: icons,
        urls: object_urls
    }

    const ocrud = ObjectCRUD("crudobj", objconfig)
    ocrud.init();

    // added event to form
    $('#id_category').on('select2:select', function (e) {
        ocrud.datatable.ajax.reload();
    })

Writing entries: ``add_log``
----------------------------

``djgentelella.history.utils.add_log`` writes one audit entry into Django's
``LogEntry`` and **returns it**:

.. code:: python

    from djgentelella.history.utils import add_log, ADDITION

    entry = add_log(
        request.user, instance, ADDITION,
        change_message='Created from the import wizard',
        related_objects=[project, (organization, {'role': 'owner'})],
        extra={'batch': 42},
    )

- ``related_objects``: a single instance, an iterable of instances, or
  ``(instance, data_dict)`` pairs. Each one becomes a ``HistoryRelation`` row
  (generic FK + optional JSON annotation) — the way to say "this action also
  touched these other objects". Bare pks are rejected: a number does not
  identify a model.
- ``extra``: an arbitrary dict stored as a relation row with no target. Query
  it back through ``LogEntry.gt_relations``.
- If ``change_message`` is empty a generic sentence is generated; a
  caller-provided message is always kept (the field list is appended on
  create/update).
- Anonymous or missing users are attributed to the account named by the
  ``GT_HISTORY_ANONYMOUS_USERNAME`` setting; without it, ``add_log`` raises
  ``ValueError`` (``LogEntry.user`` cannot be NULL).

Automatic logging: ``BaseViewSetWithLogs``
------------------------------------------

Subclass it instead of ``AuthAllPermBaseObjectManagement`` and every
create/update/destroy writes its entry. Optional knobs:

.. code:: python

    class CustomerViewSet(BaseViewSetWithLogs):
        # None (default) logs every model this viewset touches;
        # a list restricts logging to these labels.
        models_log = ['demoapp.customer']

        # Captured by default: browser, ip, method and path of the request.
        log_request_metadata = True

        def get_log_related_objects(self, instance):
            return [instance.organization]

        def get_log_extra(self, instance):
            return {'source': 'import'}

If the instance inherits ``DeletedWithTrash``, destroy soft-deletes it passing
``user=`` so the trash records who threw it away — no override needed.

Filtering by relations and extra data
-------------------------------------

``api-history-list`` understands these extra query parameters:

- ``related_contenttype=app.model`` (+ repeatable ``related_id=N``): entries
  whose relations point at those objects.
- ``extra={"org": 1, "area": 5}`` (JSON): entries whose relation payload
  contains **all** the given keys (1..n fields, matched on the same row).

Multi-tenant scoping
--------------------

``HistoryViewSet.scope_queryset(queryset)`` is the override point: it runs
last in ``get_queryset`` and ``recordsTotal`` is computed from the scoped
universe (never from the global table).

.. code:: python

    class OrgHistoryViewSet(HistoryViewSet):
        def scope_queryset(self, queryset):
            org_ct = ContentType.objects.get_for_model(Organization)
            return queryset.filter(
                gt_relations__content_type=org_ct,
                gt_relations__object_id=self.kwargs['org_pk'],
            ).distinct()
