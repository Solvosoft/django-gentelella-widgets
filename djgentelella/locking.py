"""Optimistic locking: the second of two users saving the same object gets a
clear error instead of silently overwriting the first one's changes.

Every object has a **version** (:func:`object_version`), a string that changes
whenever the object does. A form or an API client reads it along with the
object and sends it back when saving; if the row no longer has that version,
somebody else saved it in between and the save is refused.

- Forms: :class:`OptimisticLockFormMixin` (a hidden ``_version`` field and a
  non-field error), used by ``CRUDView`` with ``optimistic_lock = True``.
- DRF viewsets: :class:`OptimisticLockMixin` (``ETag`` on the detail,
  ``If-Match`` or ``_version`` on ``PUT``/``PATCH``, ``409 Conflict``).

The check re-reads the row with ``select_for_update()`` inside the
transaction of the save, so nothing can be written between the check and the
save. Everything is opt-in: a form, a view or a viewset without these mixins
behaves exactly as before.

See ``docs/source/locking.rst``.
"""

import json

from django import forms
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connections, router, transaction
from django.db.models.fields.files import FieldFile
from django.utils import formats, timezone
from django.utils.crypto import salted_hmac
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response

__all__ = [
    'VERSION_FIELD', 'ANY_VERSION', 'object_version', 'version_field',
    'version_fields', 'locked_object', 'last_change', 'conflict_message',
    'parse_if_match', 'OptimisticLockFormMixin', 'lock_form_class',
    'OptimisticLockMixin',
]

#: The name of the version in a form (hidden field) and in an API body.
VERSION_FIELD = '_version'

#: ``If-Match: *``: any version of an existing object will do.
ANY_VERSION = '*'

_SALT = 'djgentelella.locking.object_version'


class _Encoder(DjangoJSONEncoder):
    """DjangoJSONEncoder, plus what a model field may hold that it rejects."""

    def default(self, o):
        if isinstance(o, (bytes, bytearray, memoryview)):
            return bytes(o).hex()
        try:
            return super().default(o)
        except TypeError:
            return str(o)


def version_field(model):
    """The name of the field ``GTLockMeta.version_field`` declares on
    ``model`` (a class or an instance), or ``None``.

    Raises ``ImproperlyConfigured`` when it names no concrete field.
    """
    meta = getattr(model, 'GTLockMeta', None)
    name = getattr(meta, 'version_field', None)
    if not name:
        return None
    try:
        model_field = model._meta.get_field(name)
    except FieldDoesNotExist:
        model_field = None
    if model_field is None or not getattr(model_field, 'concrete', False) \
            or model_field.many_to_many:
        raise ImproperlyConfigured(
            '%s.GTLockMeta.version_field = %r is not a concrete field of the '
            'model' % (model._meta.label, name))
    return name


def version_fields(model):
    """The fields the checksum of :func:`object_version` covers: the concrete
    and editable ones, without the primary key. Many-to-many relations are
    not columns of the row and are left out; a file is its stored name."""
    return [model_field for model_field in model._meta.concrete_fields
            if model_field.editable and not model_field.primary_key]


def _value(model_field, obj):
    value = model_field.value_from_object(obj)
    if isinstance(value, FieldFile):
        return value.name or ''
    return value


def object_version(obj):
    """The version of ``obj``, as a string.

    With ``GTLockMeta.version_field`` on the model it is the value of that
    field (an integer the project increments, an ``updated_at`` with
    ``auto_now``...). Otherwise it is a checksum of the values of the
    concrete editable fields (:func:`version_fields`): stable between
    processes and independent of the order of the fields, and keyed with
    ``SECRET_KEY`` so that it says nothing about values the client cannot
    see. Computing it runs no query.
    """
    model = type(obj)
    name = version_field(model)
    if name is not None:
        value = getattr(obj, model._meta.get_field(name).attname)
        if value is None:
            return ''
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        return str(value)
    values = {model_field.attname: _value(model_field, obj)
              for model_field in version_fields(model)}
    payload = json.dumps(values, cls=_Encoder, sort_keys=True,
                         separators=(',', ':'))
    return salted_hmac(_SALT, payload, algorithm='sha256').hexdigest()[:40]


def locked_object(obj):
    """``obj`` read again from the database, locked with
    ``select_for_update()`` when inside a transaction, or ``None`` when it no
    longer exists.

    Outside a transaction (autocommit) the row is only read: a lock would
    end with the statement. Call it inside the ``transaction.atomic()`` that
    also saves, as the mixins of this module do.
    """
    model = type(obj)
    using = router.db_for_write(model, instance=obj)
    queryset = model._base_manager.using(using)
    if connections[using].in_atomic_block:
        queryset = queryset.select_for_update()
    return queryset.filter(pk=obj.pk).first()


def last_change(obj):
    """The newest ``LogEntry`` of ``obj`` (:mod:`djgentelella.history`), with
    its user, or ``None``. Only called on a conflict."""
    try:
        log_entry = apps.get_model('admin', 'LogEntry')
        content_type = apps.get_model('contenttypes', 'ContentType')
    except LookupError:
        return None
    return log_entry.objects.filter(
        content_type=content_type.objects.get_for_model(
            type(obj), for_concrete_model=False),
        object_id=str(obj.pk),
    ).select_related('user').order_by('-action_time', '-pk').first()


def conflict_message(obj):
    """What the user is told when ``obj`` changed after they read it (the
    current object, or ``None`` when it was deleted): who changed it last and
    when, if the history knows."""
    if obj is None:
        return _('This record was deleted by someone else after you opened '
                 'it. Your changes have not been saved.')
    message = _('This record was changed by someone else after you opened it. '
                'Your changes have not been saved: reload it to see the '
                'current data.')
    entry = last_change(obj)
    if entry is not None:
        user = entry.user
        full_name = getattr(user, 'get_full_name', None)
        who = ((full_name() if full_name else '') or user.get_username()) \
            if user else '?'
        when = formats.date_format(timezone.localtime(entry.action_time)
                                   if timezone.is_aware(entry.action_time)
                                   else entry.action_time, 'DATETIME_FORMAT')
        message = '%s %s' % (message, _('Last change: %(user)s, %(when)s.') % {
            'user': who, 'when': when})
    return message


def missing_message():
    return _('This record can only be saved together with the version you '
             'read. Reload it and try again.')


def parse_if_match(value):
    """The versions an ``If-Match`` header names, as a set: ``{'*'}`` for any
    version, ``None`` without the header. Weak tags (``W/"..."``) count as
    their value."""
    if value is None:
        return None
    versions = set()
    for item in value.split(','):
        item = item.strip()
        if item.startswith('W/'):
            item = item[2:]
        if len(item) >= 2 and item[0] == item[-1] == '"':
            item = item[1:-1]
        if item:
            versions.add(item)
    return versions or None


def etag(version):
    return '"%s"' % version


# -- forms ---------------------------------------------------------------------------

class OptimisticLockFormMixin:
    """For a ``ModelForm`` that edits an existing object.

    Adds a hidden ``_version`` field with the version of ``instance`` and, in
    :meth:`clean`, compares it with the row read again with
    ``select_for_update()``. A changed version is a non-field error with the
    code ``version_conflict`` (and :attr:`version_conflict` is True). An empty
    version passes unless :attr:`optimistic_lock_required`.

    Validate and save inside one ``transaction.atomic()`` for the lock to
    last until the save; ``CRUDView`` with ``optimistic_lock = True`` does.
    """

    version_field_name = VERSION_FIELD
    optimistic_lock_required = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.version_conflict = False
        instance = getattr(self, 'instance', None)
        if instance is not None and instance.pk is not None \
                and not instance._state.adding:
            self.fields[self.version_field_name] = forms.CharField(
                widget=forms.HiddenInput, required=False,
                initial=object_version(instance))

    def clean(self):
        cleaned_data = super().clean()
        self.check_version()
        return cleaned_data

    def check_version(self):
        if self.version_field_name not in self.fields:
            return
        expected = (self.cleaned_data.get(self.version_field_name) or '').strip()
        if not expected:
            if self.optimistic_lock_required:
                self.version_conflict = True
                self.add_error(None, forms.ValidationError(
                    missing_message(), code='version_required'))
            return
        current = locked_object(self.instance)
        if current is None or object_version(current) != expected:
            self.version_conflict = True
            self.add_error(None, forms.ValidationError(
                conflict_message(current), code='version_conflict'))


def lock_form_class(form_class):
    """``form_class`` with :class:`OptimisticLockFormMixin` in front (itself
    when it already has it)."""
    if issubclass(form_class, OptimisticLockFormMixin):
        return form_class
    return type(form_class.__name__, (OptimisticLockFormMixin, form_class),
                {'__module__': form_class.__module__})


# -- DRF -----------------------------------------------------------------------------

class OptimisticLockMixin:
    """For a DRF ``ModelViewSet`` (put it before the viewset class).

    - ``retrieve`` and ``get_values_for_update`` (object management) answer
      with an ``ETag`` header; ``get_values_for_update`` also carries the
      version as ``_version`` in its body, for the modals.
    - ``update``/``partial_update`` take the version they edit from
      ``If-Match`` or, without it, from ``_version`` in the body. If the row
      has another version the answer is ``409 Conflict`` with ``detail``,
      ``code`` (``version_conflict``) and the current ``version``. ``If-Match:
      *`` accepts any version.
    - Without a version the update goes on as always, unless
      :attr:`optimistic_lock_required`, which answers ``428``.

    Permissions and conditions (403) and a missing object (404) come first,
    then the version (409/428), then the validation of the data (400).
    """

    optimistic_lock_required = False
    version_field_name = VERSION_FIELD
    #: The detail actions that answer with the version.
    version_actions = ('retrieve', 'get_values_for_update')

    def get_object(self):
        obj = super().get_object()
        self._gt_lock_object = obj
        return obj

    def requested_version(self, request):
        """The versions the request edits, as a set, or ``None``."""
        versions = parse_if_match(request.headers.get('If-Match'))
        if versions is not None:
            return versions
        data = request.data
        if hasattr(data, 'get'):
            value = data.get(self.version_field_name)
            if value not in (None, ''):
                return {str(value)}
        return None

    def update(self, request, *args, **kwargs):
        expected = self.requested_version(request)
        if expected is None and not self.optimistic_lock_required:
            return super().update(request, *args, **kwargs)
        queryset = getattr(self, 'queryset', None)
        model = (queryset if queryset is not None else self.get_queryset()).model
        with transaction.atomic(using=router.db_for_write(model)):
            instance = self.get_object()
            if expected is None:
                return Response({'detail': missing_message(),
                                 'code': 'version_required'},
                                status=status.HTTP_428_PRECONDITION_REQUIRED)
            current = locked_object(instance)
            if current is None or ANY_VERSION not in expected:
                version = object_version(current) if current is not None else None
                if version not in expected:
                    response = Response(
                        {'detail': conflict_message(current),
                         'code': 'version_conflict', 'version': version},
                        status=status.HTTP_409_CONFLICT)
                    if version is not None:
                        response['ETag'] = etag(version)
                    return response
            response = super().update(request, *args, **kwargs)
            if status.is_success(response.status_code):
                saved = locked_object(instance)
                if saved is not None:
                    response['ETag'] = etag(object_version(saved))
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        obj = getattr(self, '_gt_lock_object', None)
        if obj is not None and getattr(self, 'action', None) in self.version_actions \
                and response.status_code == status.HTTP_200_OK:
            version = object_version(obj)
            response['ETag'] = etag(version)
            if self.action == 'get_values_for_update' \
                    and isinstance(getattr(response, 'data', None), dict):
                response.data[self.version_field_name] = version
        return super().finalize_response(request, response, *args, **kwargs)
