"""Notifications of a design's table: email and in-app notices.

Ported from djgentelella-editor (``gteditor.components.notifications``). A
table's ``notify`` prop lists actions that run when a row is created, updated
or deleted through its API::

    "notify": [{"on": "create", "kind": "email", "code": "product_created",
                "subject": "New product: {{ object.name }}",
                "message": "<p>{{ user.username }} added {{ object.name }}</p>",
                "to": ["actor", "sales@group.local"]},
               {"on": "update", "kind": "notice", "to": ["actor"],
                "message": "{{ object.name }} was updated."}]

``email`` goes through djgentelella.async_notification: the ``code`` names an
``EmailTemplate``, created from the design's subject and message the first
time it is sent, so an administrator can edit it afterwards. ``notice`` is a
``djgentelella.notification`` notice linking to the page.

Recipients (``to``): ``actor`` (who made the change), ``field:<path>`` (an
attribute of the row, following foreign keys: a user, or for an email an
address) and, for emails only, anything else as is: an address or an
async_notification identifier such as ``reviewers@group.local``.

**What the texts can read.** Subject and message are Django templates, but
their context is plain data, never the model instances: ``object`` holds the
row's fields the exposure allows (relations as text) and ``user`` the actor's
``username``, ``first_name``, ``last_name``, ``email`` and ``full_name``.
Template *tags* (``{% ... %}``) are only accepted from a publisher trusted with
templates (``GT_DESIGNS_ALLOW_TEMPLATES``); otherwise the texts may only print
variables.
"""

import logging

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from django.template import Context, Template, TemplateSyntaxError

from djgentelella.designs import exposure
from djgentelella.designs.builds import NotifyAction, NotifyBuild
from djgentelella.notification import create_notification

logger = logging.getLogger(__name__)

EVENTS = ['create', 'update', 'delete']
MESSAGE_TYPES = ['info', 'success', 'warning', 'danger', 'default']
CODE = r'^[a-z0-9][a-z0-9_-]*$'

NOTIFY_SCHEMA = {
    'type': 'array',
    'x-widget': 'notify',
    'title': 'Notifications',
    'items': {
        'type': 'object',
        'required': ['on', 'kind', 'to'],
        'additionalProperties': False,
        'properties': {
            'on': {'enum': EVENTS},
            'kind': {'enum': ['email', 'notice']},
            'code': {'type': 'string', 'pattern': CODE},
            'subject': {'type': 'string'},
            'message': {'type': 'string'},
            'to': {'type': 'array', 'items': {'type': 'string', 'minLength': 1},
                   'minItems': 1},
            'message_type': {'enum': MESSAGE_TYPES},
        },
    },
}


def async_notification_installed():
    return apps.is_installed('djgentelella.async_notification')


def is_user_model(model):
    return model is not None and model._meta.label == settings.AUTH_USER_MODEL


def resolve_path(model, path, rctx=None):
    """The model field at the end of ``a.b.c``, following foreign keys.

    Every step must be a field the exposure of its model allows, except a
    last step into the user model (``owner.email``): ``None`` otherwise.
    The exposures are the context's (``rctx.exposure(label)``) when there
    is one, the registered ones otherwise.
    """
    current = model
    target = None
    parts = path.split('.')
    for index, part in enumerate(parts):
        if current is None:
            return None
        if rctx is not None:
            found = rctx.exposure(current._meta.label, None)
        else:
            found = exposure.get_exposure(current)
        user_step = is_user_model(current) and index == len(parts) - 1 \
            and part in ('email', 'username')
        if not user_step and (found is None or not found.allows(part)):
            return None
        try:
            target = current._meta.get_field(part)
        except FieldDoesNotExist:
            return None
        if target.many_to_many or target.one_to_many:
            return None
        current = target.related_model if target.is_relation else None
    return target


def is_user_field(model_field):
    return (model_field is not None and model_field.is_relation
            and is_user_model(model_field.related_model))


def check_template(rctx, path, text):
    if '{%' in text and not rctx.allow_templates:
        rctx.error(path, 'template tags ({%% %%}) need a publisher trusted with '
                         'templates (GT_DESIGNS_ALLOW_TEMPLATES); use only '
                         '{{ variables }}')
        return
    try:
        Template(text)
    except TemplateSyntaxError as error:
        rctx.error(path, 'template error: %s' % error)


def resolve_notify(rctx, path, model, items):
    """Validate the ``notify`` prop; a :class:`NotifyBuild` or ``None``.

    The model and the fields the texts read come from ``rctx.exposure()``,
    the same hook the rest of the design is resolved with.
    """
    found = rctx.exposure(model._meta.label, path + '.props.notify')
    if found is None:
        return None
    build = NotifyBuild(model, fields=[model_field.name for model_field in
                                       found.model_fields()])
    codes = rctx.__dict__.setdefault('_gtdesign_email_codes', set())
    for index, item in enumerate(items):
        where = '%s.props.notify[%d]' % (path, index)
        errors_before = len(rctx.errors)
        for target in item['to']:
            if target == 'actor':
                continue
            if target.startswith('field:'):
                model_field = resolve_path(model, target[len('field:'):], rctx)
                if model_field is None:
                    rctx.error(where + '.to', '%s has no field %r a design may use'
                               % (model._meta.label, target[len('field:'):]))
                elif item['kind'] == 'notice' and not is_user_field(model_field):
                    rctx.error(where + '.to', '%r is not a user' % target)
            elif item['kind'] == 'notice':
                rctx.error(where + '.to', 'a notice goes to "actor" or a '
                                          '"field:" pointing at a user')
        if item['kind'] == 'email':
            if not async_notification_installed():
                rctx.error(where, 'email needs djgentelella.async_notification '
                                  'in INSTALLED_APPS')
                continue
            missing = [key for key in ('code', 'subject', 'message')
                       if not item.get(key)]
            if missing:
                rctx.error(where, 'an email needs %s' % ', '.join(missing))
                continue
            if item['code'] in codes:
                rctx.error(where + '.code', 'email code %r is used twice'
                           % item['code'])
            codes.add(item['code'])
            check_template(rctx, where + '.subject', item['subject'])
        elif not item.get('message'):
            rctx.error(where, 'a notice needs a message')
            continue
        check_template(rctx, where + '.message', item['message'])
        if len(rctx.errors) > errors_before:
            continue
        build.actions.append(NotifyAction(
            event=item['on'], kind=item['kind'], to=list(item['to']),
            code=item.get('code', ''), subject=item.get('subject', ''),
            message=item.get('message', ''),
            message_type=item.get('message_type', 'info')))
    return build if build.actions else None


# -- running them ---------------------------------------------------------------

def value_at(instance, path):
    """``instance.a.b`` for ``'a.b'``, or None anywhere along the way."""
    for part in path.split('.'):
        if instance is None:
            return None
        instance = getattr(instance, part, None)
    return instance


def object_context(build, instance):
    """The row as the texts see it: its allowed fields, as plain values."""
    data = {'pk': instance.pk}
    for name in build.fields:
        model_field = instance._meta.get_field(name)
        if model_field.many_to_many:
            value = ', '.join(str(item) for item in getattr(instance, name).all()) \
                if instance.pk is not None else ''
        elif model_field.choices:
            value = getattr(instance, 'get_%s_display' % name)()
        else:
            value = getattr(instance, name, None)
            if model_field.is_relation and value is not None:
                value = str(value)
        data[name] = value
    return data


def user_context(user):
    if user is None or not user.is_authenticated:
        return {}
    return {'username': user.get_username(), 'first_name': user.first_name,
            'last_name': user.last_name, 'email': user.email,
            'full_name': user.get_full_name()}


def targets(names, instance, user):
    """Resolve ``actor``, ``field:<path>`` and literal recipients."""
    found = []
    for name in names:
        if name == 'actor':
            found.append(user)
        elif name.startswith('field:'):
            found.append(value_at(instance, name[len('field:'):]))
        else:
            found.append(name)
    return [target for target in found if target]


def addresses(names, instance, user):
    """Email addresses: users give their email, strings pass through."""
    found = [getattr(target, 'email', target)
             for target in targets(names, instance, user)]
    return [address for address in found if isinstance(address, str) and address]


def render(text, context, autoescape=True):
    return Template(text).render(Context(context, autoescape=autoescape))


def send_email(action, recipients, context, user):
    # Optional app: the design only validates when it is installed.
    from djgentelella.async_notification.models import EmailTemplate  # noqa: PLC0415
    from djgentelella.async_notification.sending import (  # noqa: PLC0415
        send_email_from_template,
    )
    EmailTemplate.objects.get_or_create(code=action.code, defaults={
        'subject': action.subject, 'message': action.message})
    send_email_from_template(action.code, recipients, context,
                             user=user if user is not None
                             and user.is_authenticated else None)


def notify(build, event, instance, user, link=None):
    """Run the actions of ``build`` for ``event`` on ``instance``.

    The texts and recipients are read now -- a deleted row is still there --
    and sent once the transaction commits. A failing action is logged; it
    never undoes the change the user made.
    """
    context = {'object': object_context(build, instance), 'user': user_context(user)}
    jobs = []
    for action in build.actions_for(event):
        if action.email:
            recipients = addresses(action.to, instance, user)
            if recipients:
                jobs.append((send_email, (action, recipients, context, user)))
        else:
            message = render(action.message, context)
            for target in targets(action.to, instance, user):
                if isinstance(target, get_user_model()):
                    jobs.append((create_notification, (
                        message, target, action.message_type), {'link': link}))

    def run():
        for job in jobs:
            function, args = job[0], job[1]
            kwargs = job[2] if len(job) > 2 else {}
            try:
                function(*args, **kwargs)
            except Exception:  # noqa: BLE001 -- a notice must not break a save
                logger.exception('Design notification %s of %s failed', event,
                                 build.model._meta.label)

    transaction.on_commit(run)
