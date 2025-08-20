Trash functionality
===========================

Introduction
------------------

The **Trash** feature enables both logical deletion and permanent deletion of objects.
Combined with **History**, it provides full control over data management, including recovery and auditing of deleted records.

Model Integration
-----------------------

To enable trash management in your models, inherit from ``DeletedWithTrash``.
This abstract class is related to the ``Trash`` model and provides the necessary logic.

.. code:: python

    from djgentelella.models import DeletedWithTrash

    class Customer(DeletedWithTrash):
        name = models.CharField(max_length=150)
        phone_number = models.CharField(max_length=150)
        email = models.EmailField()

        def __str__(self):
            return self.name

        def delete(self, using=None, keep_parents=False, *, hard=False, user=None, **kwargs):
            if self.is_deleted and not hard:
                return

            result = super().delete(
                using=using, keep_parents=keep_parents,
                hard=hard, user=user
            )
            return result

ViewSets and Deletion
---------------------------

There are two possible cases when overriding ``perform_destroy`` in your ViewSet:

**Case 1: Without history**

.. code:: python

    def perform_destroy(self, instance):
        instance.delete(user=self.request.user)

**Case 2: With history**

.. code:: python

    from djgentelella.history.api import BaseViewSetWithLogs
    from djgentelella.history.utils import add_log, DELETION

    class CustomerViewSet(BaseViewSetWithLogs):
        ...
        def perform_destroy(self, instance):
            # add log for history
            add_log(
                self.request.user,
                instance,
                DELETION,
                "customer",
                [],
                change_message=_("Deleted"),
            )
            # add user to deleted_by for trash
            instance.delete(user=self.request.user)

In both cases, you must override the ``perform_destroy`` method.

Forms
------------------

When using forms, you should exclude the ``is_deleted`` field:

.. code:: python

    from djgentelella.forms.forms import GTForm
    import djgentelella.widgets.core as gtw

    class CustomerForm(GTForm, forms.ModelForm):
        class Meta:
            model = Customer
            fields = "__all__"
            exclude = ["is_deleted"]
            widgets = {
                "name": gtw.TextInput,
                "email": gtw.EmailInput,
                "phone_number": gtw.PhoneNumberMaskInput,
            }

Template Example
------------------------

Example HTML template for Trash:

.. code:: html+django

    <div class="card mt-2">
        <div class="card-body">
            <div class="card-title titles">
                <h2 class="text-center"> {% trans 'Trash' %} </h2>
            </div>

            <div class="row mt-3 ">
                <div class="col-12">
                    <table class="table table-hover table-striped w-100 table-responsive" id="table-trash">
                    </table>
                </div>
            </div>
        </div>
    </div>

    {# Modals actions #}
    {% url "api-trash-list" as list_trash_url %}

    {% trans 'Delete Instance' as delete_trash_tittle %}
    {% include 'gentelella/blocks/modal_template_delete.html'
        with form=form_delete form_id="delete_trash_form"
        id="delete_trash_modal" title=delete_trash_tittle
        url=detail_trash_url %}

JavaScript Initialization
---------------------------------

.. code:: javascript

    const trash_urls = {
        list_url: "{% url 'api-trash-list' %}",
        restore_url: "{% url "api-trash-restore"  0 %}",
        destroy_url: "{% url "api-trash-detail"  0 %}",
    }

    const modal_trash_ids = {
        destroy: "#delete_trash_modal",
    }

    const actions_trash = {
        table_actions: [],
        object_actions: [
            {
                'name': "restore",
                'action': 'restore',
                'in_action_column': true,
                'i_class': 'fa fa-undo',
                'method': 'POST',
                'title': gettext("Restore"),
                data_fn: function (data) {
                    return data;
                }
            }
        ],
        title: 'Actions',
        className: "no-export-col"
    }

    const datatable_trash_inits = {
        columns: [
            {data: "id", name: "id", title: "ID", type: "string", visible: false},
            {
                data: "created_at",
                name: "created_at",
                title: gettext("Deleted Date"),
                visible: true,
                type: "date",
                dateformat: document.datetime_format
            },
            {
                data: "deleted_by",
                name: "deleted_by",
                title: gettext("Deleted by"),
                type: "readonly",
                visible: true,
            },
            {
                data: "object_repr",
                name: "object_repr",
                title: gettext("Description"),
                type: "readonly",
                visible: true,
            },
            {
                data: "model_name",
                name: "content_type__model",
                title: gettext("Model"),
                type: "readonly",
                visible: true,
            },
            {
                data: "actions",
                name: "actions",
                title: gettext("Actions"),
                type: "string",
                visible: true,
            },
        ],
        addfilter: true,
    }

    const trash_config = {
        datatable_element: "#table-trash",
        modal_ids: modal_trash_ids,
        actions: actions_trash,
        datatable_inits: datatable_trash_inits,
        add_filter: true,
        relation_render: {'field_autocomplete': 'text'},
        delete_display: data => {
            return `${gettext("Registration ID")}: ${data['id']} <br>
                    ${gettext('Model')}: ${data["model_name"]} <br>
                    <span class="text-danger">
                        ${gettext("This action will permanently delete the register, as well as all related data.")}
                    </span>`;
        },
        icons: icons,
        urls: trash_urls,
    }

    const trash_crud = ObjectCRUD("trashcrudobj", trash_config)

    trash_crud.restore = function (data) {
        const url = trash_urls.restore_url.replace("0", data.id)

        $.ajax({
            url: url, type: "POST", data: {}, headers: {
                "X-CSRFToken": getCookie('csrftoken'),
            }, success: function (response) {
                if (response.result) {
                    Swal.fire({
                        icon: 'success',
                        title: gettext('Success'),
                        text: gettext(response.detail),
                        confirmButtonText: gettext('Accept'),
                    })

                    ocrud.datatable.ajax.reload() // only for example
                    trash_crud.datatable.ajax.reload()
                } else {
                    window.location.reload();
                }
            }, error: function (xhr, status, error) {
                console.error("Error executing the API:", error);

                Swal.fire({
                    icon: 'error',
                    title: gettext('Error'),
                    text: gettext("Sorry, an error occurred."),
                    confirmButtonText: gettext('Accept'),
                })
            }
        });
    }

    trash_crud.init();

Object Managers
----------------------

When inheriting from ``DeletedWithTrash``, three different managers are available to handle objects:

- ``objects = ObjectManager()`` → Returns **only non-deleted objects**.
- ``objects_with_deleted = AllObjectsManager()`` → Returns **all objects, including deleted**.
- ``objects_deleted_only = DeletedObjectsManager()`` → Returns **only deleted objects**.

This allows flexible querying and management of your application data.
