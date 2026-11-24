"""
Which document the digital signature may read, and who may read it.

The signature widget puts in the page a reference to the file it signs: the
content type, the primary key and the name of the file field. That reference
comes back from the browser to the preview endpoint, to the signing websocket
and to the form, so it is signed here with ``django.core.signing`` and only a
reference issued by the server is accepted. A value the client wrote itself
can only carry an upload token, which ``find_upload`` already ties to who
uploaded it.

A valid reference is not permission: who uses it still has to be allowed to
reach that object, see :func:`has_document_access`.
"""
import base64
import binascii
import json
import logging

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils.module_loading import import_string

logger = logging.getLogger('djgentelella')

#: Salt of the signed references, only used for them.
REFERENCE_SALT = 'djgentelella.firmador_digital.document_reference'

#: What the user does with the document.
VIEW = 'view'
SIGN = 'sign'


def _json_pk(pk):
    return pk if isinstance(pk, (int, str)) else str(pk)


def sign_document_reference(instance, field_name):
    """The signed value that names ``field_name`` of ``instance``."""
    return signing.dumps(
        {
            'contenttype': ContentType.objects.get_for_model(instance).pk,
            'pk': _json_pk(instance.pk),
            'field_name': field_name,
        },
        salt=REFERENCE_SALT,
    )


def load_document_reference(value):
    """
    The ``{contenttype, pk, field_name}`` of a reference signed by
    :func:`sign_document_reference`, or ``None`` if ``value`` is not one,
    was tampered with or expired (``FIRMADOR_REFERENCE_MAX_AGE``).
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        data = signing.loads(
            value, salt=REFERENCE_SALT,
            max_age=getattr(settings, 'FIRMADOR_REFERENCE_MAX_AGE', None),
        )
    except signing.BadSignature:
        return None
    if not isinstance(data, dict) or not {'contenttype', 'pk', 'field_name'} <= set(
            data):
        return None
    return data


def decode_document_value(value):
    """
    The value the widget sends back, decoded.

    Either a signed reference (``{contenttype, pk, field_name}``) or the
    base64 JSON ``{"token": ...}`` the browser builds after signing. Anything
    else -- an unsigned ``field_name`` above all -- gives ``None``.
    """
    reference = load_document_reference(value)
    if reference is not None:
        return reference
    try:
        data = json.loads(base64.b64decode(value.encode()).decode())
    except (AttributeError, binascii.Error, UnicodeError, ValueError):
        return None
    if not isinstance(data, dict) or 'token' not in data:
        if isinstance(data, dict) and 'field_name' in data:
            logger.warning('Digital signature: unsigned document reference '
                           'rejected')
        return None
    return {'token': data['token']}


def same_object(reference, cc, pk):
    """Whether the reference names the content type and pk given apart (the
    URL of the preview, the ``cc``/``pk`` of the websocket)."""
    return (str(reference['contenttype']) == str(cc)
            and str(reference['pk']) == str(pk))


def get_reference_instance(reference):
    """The object of a signed reference, or ``None`` if it is gone."""
    try:
        model = ContentType.objects.get_for_id(
            reference['contenttype']).model_class()
        if model is None:
            return None
        return model._base_manager.get(pk=reference['pk'])
    except (ObjectDoesNotExist, ValidationError, ValueError, TypeError):
        return None


def default_document_access(user, instance, field_name, action):
    """
    The default rule: signing needs ``change`` on the model (or on the object,
    with an object permission backend); the preview takes ``view`` or
    ``change``, as the Django admin does.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    opts = instance._meta
    perms = ['change'] if action == SIGN else ['view', 'change']
    for perm in perms:
        name = '%s.%s_%s' % (opts.app_label, perm, opts.model_name)
        if user.has_perm(name) or user.has_perm(name, instance):
            return True
    return False


def has_document_access(user, instance, field_name, action):
    """
    Whether ``user`` may ``action`` (:data:`VIEW` or :data:`SIGN`) the file in
    ``field_name`` of ``instance``.

    The preview endpoint and the signing websocket both ask here. A project
    replaces the rule with ``FIRMADOR_ACCESS_CHECK``, the dotted path of a
    callable with this same signature.
    """
    check = getattr(settings, 'FIRMADOR_ACCESS_CHECK', None)
    check = import_string(check) if check else default_document_access
    return bool(check(user, instance, field_name, action))
