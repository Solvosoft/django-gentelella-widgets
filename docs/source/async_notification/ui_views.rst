Management UI
===========================

The module provides server-rendered HTML pages for managing all async_notification entities.
Each page uses DataTables for listing, Bootstrap 5 modals for CRUD operations, and the
``ObjectCRUD`` JavaScript framework from djgentelella.

Email Templates Page
-----------------------

**URL:** ``/email-templates/``

**Features:**

- DataTable listing templates with code, subject, and creation date.
- Create/Update modals with a two-column layout:

  - **Left column:** Form with code, subject, message (TinyMCE editor), BCC, CC, context code, and base template selectors.
  - **Right column:** Model Inspector showing available template variables, and a live Preview panel.

- Preview from table: clicking the eye icon on a row renders the template with dummy data from the saved ``context_code``.
- Delete modal with confirmation.

**Template:** */djgentelella/async_notification/templates/async_notification/email_template.html*

The Model Inspector panel updates dynamically when the ``context_code`` select changes,
fetching field descriptions from the ``/model-fields/`` endpoint as an HTML fragment.

The Preview button extracts the current TinyMCE content, ``context_code``, and ``base_template``
values from the modal and sends them to the ``/preview-template/`` endpoint.

Email Notifications Page
---------------------------

**URL:** ``/email-notifications/``

**Features:**

- DataTable listing notifications with subject, status, sent flag, enqueued flag, retry count, created date, and user.
- Create/Update modals with TinyMCE editor for the message body.
- Recipient autocomplete on the recipients, CC, and BCC input fields.
- "Send Selected" table action for batch sending.
- "Send Now" row action for immediate sending of individual notifications.
- Delete modal with confirmation.
- Checkable rows for bulk operations.

**Template:** */djgentelella/async_notification/templates/async_notification/email_notification.html*

Recipient Autocomplete
^^^^^^^^^^^^^^^^^^^^^^^^^

When typing in the recipients, CC, or BCC fields, a debounced autocomplete dropdown appears after 2 characters.
It fetches suggestions from the ``/autocomplete/`` endpoint, which searches:

- All registered recipient resolvers (e.g., Django groups).
- The User model by username, email, first name, and last name.

Clicking a suggestion appends the value to the field as a comma-separated entry.

Newsletters Page
-------------------

**URL:** ``/newsletters/``

**Features:**

- DataTable listing newsletters with subject, template title, creator, and creation date.
- Create/Update modals with Select2 autocomplete for the template field.
- TinyMCE editor for the message body.
- Recipient autocomplete on recipients, CC, and BCC fields.
- "Preview Recipients" row action that resolves all recipients and shows the list in a modal.
- Delete modal with confirmation.

**Template:** */djgentelella/async_notification/templates/async_notification/newsletter.html*

The ``template`` field uses a Select2 widget (``AutocompleteSelect``) that searches newsletter templates
by title via the ``/newslettertemplate/`` API endpoint.

Newsletter Templates Page
----------------------------

**URL:** ``/newsletter-templates/``

**Features:**

- DataTable listing templates with title, slug, model base, and creation date.
- Create/Update modals with TinyMCE editor.
- Model base selector populated from ``ASYNC_NEWS_BASE_MODELS`` settings.
- Delete modal with confirmation.

**Template:** */djgentelella/async_notification/templates/async_notification/newsletter_template.html*

Newsletter Tasks Page
------------------------

**URL:** ``/newsletter-tasks/``

**Features:**

- DataTable listing tasks with newsletter subject, send date, status, and creation date.
- Create/Update modals with Select2 autocomplete for the newsletter field and a DateTimeInput for send date.
- Backend scheduling: creating a task automatically calls ``backend.schedule()``, updating revokes and reschedules, deleting revokes.
- Delete modal with confirmation.

**Template:** */djgentelella/async_notification/templates/async_notification/newsletter_task.html*

The ``newsletter`` field uses a Select2 widget that searches newsletters by subject via the ``/newsletter/`` API endpoint.

TinyMCE Integration
-----------------------

All message fields use the ``EditorTinymce`` widget, which provides:

- Full WYSIWYG editing with toolbar for formatting, lists, links, images, media, and code.
- Image upload via ``/upload-image/`` endpoint.
- Video upload via ``/upload-video/`` endpoint.

.. note::

    When TinyMCE is used inside Bootstrap 5 modals, a global ``focusin`` listener in ``widgets.js`` prevents
    Bootstrap from stealing focus when TinyMCE opens its own dialogs (e.g., insert link, insert image).
    This is handled automatically.

Upload File Reassociation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When creating a new entity, uploaded files initially have ``object_id=0`` because the entity doesn't exist yet.
The upload views accept an optional ``upload_session`` parameter to track files. After the entity is saved,
files can be reassociated via the ``/reassociate-files/`` endpoint:

.. code:: javascript

    // After saving the entity, reassociate uploaded files
    fetch('/async_notification/reassociate-files/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: 'upload_session=' + sessionId +
              '&object_id=' + newEntityId +
              '&content_type=async_notification.emailnotification'
    });

Orphaned files (``object_id=0``, older than 24 hours) are automatically cleaned up by the
``process_notifications`` management command.

API ViewSets
--------------

All CRUD operations are handled through DRF ViewSets extending ``AuthAllPermBaseObjectManagement``:

- ``EmailNotificationManagement`` - CRUD + ``send_email`` + ``send_selected`` actions.
- ``EmailTemplateManagement`` - CRUD + ``preview`` action.
- ``NewsLetterTemplateManagement`` - Standard CRUD.
- ``NewsLetterManagement`` - CRUD + ``preview`` + ``preview_recipients`` actions.
- ``NewsLetterTaskManagement`` - CRUD with automatic backend scheduling/revoking.

All ViewSets use:

- ``LimitOffsetPagination`` for DataTable server-side pagination.
- ``DjangoFilterBackend``, ``SearchFilter``, and ``OrderingFilter`` for filtering and sorting.
- Per-action permission dictionaries mapping actions to Django model permissions.

Serializers follow the DataTable wrapper pattern with separate serializers for list (table), create, and detail views.
