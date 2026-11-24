==================
Optimistic locking
==================

Two users open the same record, both change it and both save: without a
lock, the second save silently overwrites the first one. With
``djgentelella.locking`` the second user gets a clear error instead, and can
reload the form with the current data.

It is *optimistic*: nothing is locked while somebody edits. The form or the
API client keeps the **version** of the object it read and sends it back with
its changes; if the object no longer has that version, somebody else saved it
in between and the save is refused.

It is a plain module of ``djgentelella``: nothing to add to
``INSTALLED_APPS``, no migration. Everything is **off by default**: a form, a
``CRUDView`` or a viewset that does not ask for it renders the same HTML,
answers the same responses and runs the same queries as before.


The version of an object
========================

.. code:: python

    from djgentelella.locking import object_version

    object_version(customer)   # '3be045dfe71713e470eb007c3fe81c8a338c3d9e'

``object_version(obj) -> str`` runs no query. It is one of two things:

**A version field the model declares**, with ``GTLockMeta``:

.. code:: python

    class Customer(models.Model):
        name = models.CharField(max_length=100)
        updated_at = models.DateTimeField(auto_now=True)

        class GTLockMeta:
            version_field = 'updated_at'

The version is the value of that field (``isoformat()`` for dates and
datetimes, the text of anything else). **djgentelella never writes it**: the
project keeps it current, with ``auto_now`` or in the model's ``save()``:

.. code:: python

    class Contract(models.Model):
        version = models.PositiveIntegerField(default=0, editable=False)

        class GTLockMeta:
            version_field = 'version'

        def save(self, *args, **kwargs):
            self.version += 1
            super().save(*args, **kwargs)

The reason: a version is only worth something if *every* write changes it --
the admin, a management command, a flow action, the shell. Only the model
sees all of them. If the lock incremented the field itself, every other way
of saving would leave it untouched and the lock would wrongly report "no
change". (``QuerySet.update()`` skips ``save()`` and ``auto_now`` alike: a
bulk update has to set the field itself.) A ``GTLockMeta.version_field`` that
is not a concrete field of the model raises ``ImproperlyConfigured``.

**Otherwise, a checksum** of the values of the model's concrete and editable
fields, without the primary key (``version_fields(model)``):

- it is stable between processes and servers -- it is an HMAC-SHA256 of the
  values serialized as JSON with sorted keys, not ``hash()`` -- and does not
  depend on the order of the fields;
- it is keyed with ``SECRET_KEY`` (``salted_hmac``), so the version says
  nothing about values the client is not allowed to see, such as a column
  hidden by a condition. Changing ``SECRET_KEY`` changes every version once:
  a form open at that moment gets one spurious conflict;
- a foreign key counts by its id;
- **a file counts by its stored name**, not by its content: replacing the
  file under the same name is not a change;
- **many-to-many relations are left out**: they are not columns of the row,
  ``select_for_update()`` does not lock them, and reading them would cost a
  query per relation on every check. A change of only the tags of a product
  is not a conflict. A model where that matters declares a version field
  and bumps it when its relations change;
- fields with ``editable=False`` are left out, ``auto_now`` ones included
  (declare one of them as the version field to use it).


Forms
=====

``OptimisticLockFormMixin`` goes in front of a ``ModelForm``:

.. code:: python

    from djgentelella.locking import OptimisticLockFormMixin

    class CustomerForm(OptimisticLockFormMixin, GTForm, forms.ModelForm):
        class Meta:
            model = Customer
            fields = ['name', 'credit_limit']

    # or, for a form class you do not own:
    LockedForm = lock_form_class(CustomerForm)

Editing an existing object, the form gets a hidden ``_version`` field with
the version of ``instance``. In ``clean()`` it reads the row again with
``select_for_update()`` and compares: if the version changed, the form has a
non-field error with the code ``version_conflict`` and ``form.version_conflict``
is ``True``. The message is translated and, when :doc:`history` has an entry
for the object, says who changed it last and when ("Last change: Ana Mora,
23 Nov 2026 10:41."). That lookup runs only on a conflict: a save without a
conflict makes no query to the history.

A form posted without ``_version`` is not checked, unless
``optimistic_lock_required = True`` (error code ``version_required``). A
creation form has no object and no version field.

**The transaction.** The lock taken by ``select_for_update()`` lasts until
the end of the transaction, so validate and save inside the same
``transaction.atomic()``:

.. code:: python

    with transaction.atomic():
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()

Then a second save that arrives while the first one is still running waits
for it, reads the new version and is refused: there is no window between the
check and the write. Outside a transaction the row is only read (a lock would
end with the statement). SQLite has no row locks; its writes are serialized
by the database lock instead.


CRUDView
========

.. code:: python

    class CustomerCRUD(CRUDView):
        model = Customer
        optimistic_lock = True

The update view uses its form (``update_form`` or the generated one) with
``OptimisticLockFormMixin`` and runs the whole ``POST`` inside one
transaction. On a conflict the page shows the form again with the error and a
link that reloads it with the current data; the user's values stay in the
form so they can be copied. The permissions and the ``action_conditions`` of
the view are checked first: a refused update is a 403 whatever the version.


DRF viewsets
============

.. code:: python

    from djgentelella.locking import OptimisticLockMixin

    class CustomerViewSet(OptimisticLockMixin, viewsets.ModelViewSet):
        queryset = Customer.objects.all()
        serializer_class = CustomerSerializer

- ``GET`` of the detail (``retrieve``) answers with an ``ETag`` header,
  ``"<version>"``. ``get_values_for_update`` of an object management viewset
  carries it too, plus ``_version`` in its body.
- ``PUT`` and ``PATCH`` take the version they edit from ``If-Match`` or,
  without that header, from a ``_version`` field of the body. ``If-Match:
  *`` accepts any version; weak tags (``W/"..."``) count as their value.
- If the row has another version the answer is **409 Conflict**:

  .. code:: json

      {"detail": "This record was changed by someone else after you opened it. ...",
       "code": "version_conflict",
       "version": "<current version>"}

  with the current version in ``ETag`` too. A successful update answers with
  the new ``ETag``.
- Without ``If-Match`` and without ``_version`` the update goes on as it
  always did, unless ``optimistic_lock_required = True``: then it is **428
  Precondition Required** (``"code": "version_required"``).

The order is fixed: authentication, permissions and conditions (403) and a
missing object (404) first, then the version (409, 428), then the validation
of the data (400). The check and the save run in one transaction, with the
row locked, and a ``PATCH`` saves over the row read after the lock: the
fields it does not send keep the values of the latest save.


Designs: ``object_management``
==============================

The ``object_management`` and ``inline_object_management`` components of
:doc:`designs` take the prop ``optimistic_lock`` (a boolean, ``false`` by
default):

.. code:: json

    {"type": "object_management", "id": "products",
     "props": {"model": "ventas.Producto", "form": "producto",
               "optimistic_lock": true}}

The table's viewset gets ``OptimisticLockMixin`` (after the conditions of the
table, so a refused row is still a 403). The page is the same: the version
travels with the API. When the update modal is filled
(``get_values_for_update``) it keeps the ``_version`` it read and sends it
with the ``PUT``. On a 409 the modal stays open and a dialog explains what
happened, offering to **reload the form with the current data** -- or to keep
the user's values on screen, to copy them before reloading.

The same JavaScript (``obj_api_management.js``, ``ObjectCRUD``) works with
any ``BaseObjectManagement`` viewset that has ``OptimisticLockMixin``: it
only acts when ``get_values_for_update`` sends a ``_version``.


Reference
=========

``djgentelella.locking``:

``object_version(obj) -> str``
    The version of ``obj``.
``version_field(model) -> str | None`` / ``version_fields(model) -> list``
    The declared version field; the fields of the checksum.
``locked_object(obj)``
    The row read again, locked with ``select_for_update()`` inside a
    transaction; ``None`` if it was deleted.
``conflict_message(obj)`` / ``last_change(obj)``
    The translated message of a conflict and the ``LogEntry`` it quotes.
``parse_if_match(value) -> set | None``
    The versions of an ``If-Match`` header.
``OptimisticLockFormMixin`` / ``lock_form_class(form_class)``
    Forms: ``version_field_name`` (``'_version'``),
    ``optimistic_lock_required``, ``version_conflict``.
``OptimisticLockMixin``
    Viewsets: ``optimistic_lock_required``, ``version_field_name``,
    ``version_actions`` (``('retrieve', 'get_values_for_update')``),
    ``requested_version(request)``.
``VERSION_FIELD`` / ``ANY_VERSION``
    ``'_version'`` and ``'*'``.
