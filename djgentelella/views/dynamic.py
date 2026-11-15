"""Endpoints of the dynamic actions runtime and of the LOVs.

``dynamic_action_view`` runs a ``set_value(server=...)`` form method. The
browser sends ``{"token": ..., "data": {field: value}}``; the token is the
signed ``(form path, method)`` GTForm rendered, and the method must still be
declared in the ``dynamic_actions`` of that class, so neither an arbitrary form
nor an arbitrary method can be reached. The token expires
(``GT_DYNAMIC_ACTIONS_MAX_AGE``), is refused for another user when it was bound
to one, and ``Form.dynamic_actions_has_permission(request, method)`` decides who
may run it.

``lov_view`` serves a registered LOV in the select2 format.
"""

import json

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.forms import BaseForm
from django.http import JsonResponse
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from djgentelella.forms.dynamic import load_token, server_methods
from djgentelella.lov import get_lov

MAX_FIELDS = 500
MAX_QUERY = 200
# Keeps OFFSET inside a bigint and away from absurd scans.
MAX_PAGE = 10000


def _error(message, status):
    return JsonResponse({'error': message}, status=status)


def _valid_scalar(value):
    return value is None or isinstance(value, (str, bool, int, float))


def _valid_data(data):
    if not isinstance(data, dict) or len(data) > MAX_FIELDS:
        return False
    for key, value in data.items():
        if not isinstance(key, str):
            return False
        if isinstance(value, list):
            if not all(_valid_scalar(item) for item in value):
                return False
        elif not _valid_scalar(value):
            return False
    return True


@require_POST
def dynamic_action_view(request):
    try:
        body = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return _error(_('The body is not valid json.'), 400)
    if not isinstance(body, dict):
        return _error(_('The body must be a json object.'), 400)
    token = body.get('token')
    data = body.get('data', {})
    if not isinstance(token, str) or not _valid_data(data):
        return _error(_('Expected {"token": str, "data": {field: value}}.'), 400)

    try:
        payload = load_token(token)
    except signing.SignatureExpired:
        return _error(_('The form expired, reload the page.'), 403)
    except signing.BadSignature:
        return _error(_('Invalid signature.'), 403)
    path, method = payload['form'], payload['method']
    if 'user' in payload and (not request.user.is_authenticated
                              or str(request.user.pk) != payload['user']):
        return _error(_('This form was rendered for another user.'), 403)
    try:
        form_class = import_string(path)
    except ImportError:
        return _error(_('Unknown form.'), 400)
    if not isinstance(form_class, type) or not issubclass(form_class, BaseForm):
        return _error(_('Unknown form.'), 400)
    # Checked again at request time: a token signed for a method that has since
    # left dynamic_actions stops working.
    if method not in server_methods(form_class) \
            or not callable(getattr(form_class, method, None)):
        return _error(_('Method not declared in dynamic_actions.'), 403)
    has_permission = getattr(form_class, 'dynamic_actions_has_permission', None)
    if has_permission is not None:
        if not has_permission(request, method):
            return _error(_('Permission denied.'), 403)
    elif not getattr(form_class, 'dynamic_actions_public', False) \
            and not request.user.is_authenticated:
        return _error(_('Authentication required.'), 403)

    factory = getattr(form_class, 'dynamic_actions_instance', None)
    form = factory(request) if factory is not None else form_class()
    try:
        result = getattr(form, method)(data)
    except ValidationError as error:
        return JsonResponse({'errors': error.messages}, status=400)
    except PermissionDenied:
        return _error(_('Permission denied.'), 403)
    if not isinstance(result, dict):
        raise TypeError('%s.%s must return a dict {field: value}, got %r'
                        % (form_class.__name__, method, result))
    values = {key: value for key, value in result.items() if key in form.fields}
    return JsonResponse(values, encoder=DjangoJSONEncoder)


@require_GET
def lov_view(request, name):
    try:
        lov = get_lov(name)
    except LookupError:
        return _error(_('Unknown list of values.'), 404)
    if not lov.has_permission(request):
        return _error(_('Permission denied.'), 403)
    try:
        page = int(request.GET.get('page', 1))
    except ValueError:
        return _error(_('page must be an integer.'), 400)
    if not 1 <= page <= MAX_PAGE:
        return _error(_('page must be between 1 and %(max)d.') % {'max': MAX_PAGE},
                      400)
    q = request.GET.get('q', request.GET.get('term', ''))[:MAX_QUERY]
    parents = {key: request.GET.get(key) for key in lov.depends_on}
    rows, more = lov.page(request, parents, q, page)
    return JsonResponse({
        'results': [{'id': value, 'text': label} for value, label in rows],
        'pagination': {'more': more},
    }, encoder=DjangoJSONEncoder)
