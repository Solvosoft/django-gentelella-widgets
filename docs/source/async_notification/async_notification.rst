Async Notifications
===========================

The **Async Notification** module (``djgentelella.async_notification``) provides a complete email notification and newsletter system
for Django projects. It supports template-based emails, recipient resolution, scheduled newsletters, file attachments,
and both synchronous and Celery-based sending backends.

Features
-----------

- **Email Templates** with Django template syntax and live preview
- **Email Notifications** with queued or immediate sending
- **Newsletters** with template composition and scheduled delivery
- **Recipient Resolution** with custom resolver backends (groups, roles, etc.)
- **Model Introspection** for template variable suggestions
- **File Attachments** with inline image support
- **Management Commands** for processing, inspection, and demo data
- **Admin UI** with DataTables, modals, autocomplete, and Select2 widgets

.. toctree::
   :maxdepth: 2

   installation
   backends
   settings
   models
   sending
   templates_and_preview
   newsletters
   resolvers
   registry
   management_commands
   ui_views
