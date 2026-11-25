from django.conf import settings
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _

HARD_DELETION = 4
RESTORE = 5
#: Somebody (or the system) read a secret: a credential, a key, a password.
SECRET_READ = 6

#: ``{action_flag: label}`` of every action the history knows: Django's
#: three, djgentelella's and those added with :func:`register_action`.
ACTIONS = {
    ADDITION: _('created'),
    CHANGE: _('updated'),
    DELETION: _('deleted'),
    HARD_DELETION: _('hard deleted'),
    RESTORE: _('restored'),
    SECRET_READ: _('secret read'),
}
#: The flags djgentelella defines; :func:`register_action` cannot change them.
BUILTIN_ACTIONS = frozenset(ACTIONS)
#: The account a system event is attributed to, by default.
DEFAULT_SYSTEM_USERNAME = 'gt-system'
#: Keys :func:`add_log` writes in the ``extra`` of a system event.
SYSTEM_KEY, ACTOR_KEY = 'gt_system', 'gt_actor'


def register_action(action_flag, label):
    """Add an action to the history (:data:`ACTIONS`): ``add_log`` takes its
    flag, the history shows ``label`` and its filter offers it.

    ``action_flag`` is a positive integer that is not one of
    :data:`BUILTIN_ACTIONS`; use values from 100 up, apart from any
    djgentelella may add later. Registering the same flag again with
    another label is an error (two apps that chose the same number).
    Returns ``action_flag``, so a module can write
    ``USED = register_action(100, _('used'))``.
    """
    if not isinstance(action_flag, int) or isinstance(action_flag, bool) \
            or action_flag <= 0:
        raise ValueError('action_flag must be a positive integer, not %r'
                         % (action_flag,))
    if action_flag in BUILTIN_ACTIONS:
        raise ValueError("action_flag %d is one of djgentelella's own actions"
                         % action_flag)
    known = ACTIONS.get(action_flag)
    if known is not None and str(known) != str(label):
        raise ValueError('action_flag %d is already registered as %r'
                         % (action_flag, str(known)))
    ACTIONS[action_flag] = label
    return action_flag


def action_label(action_flag):
    """The label of ``action_flag`` (:data:`ACTIONS`), or the number."""
    return ACTIONS.get(action_flag, str(action_flag))


def action_choices():
    """``[(flag, label)]`` of :data:`ACTIONS`, read when asked: an action
    registered after import shows up."""
    return [(flag, str(label)) for flag, label in ACTIONS.items()]


def system_user():
    """The account system events are written with (:func:`add_log`
    ``system=True``): ``GT_HISTORY_SYSTEM_USERNAME``, ``'gt-system'`` by
    default.

    ``LogEntry.user`` cannot be empty, so the account exists: when it does
    not, it is created inactive and without a usable password -- nobody can
    sign in with it. A user model that needs more than the username to
    create one has to create the account itself.
    """
    username = getattr(settings, 'GT_HISTORY_SYSTEM_USERNAME', None) \
        or DEFAULT_SYSTEM_USERNAME
    model = get_user_model()
    found = model._default_manager.filter(**{model.USERNAME_FIELD: username}).first()
    if found is not None:
        return found
    account = model(**{model.USERNAME_FIELD: username})
    if hasattr(account, 'is_active'):
        account.is_active = False
    account.set_unusable_password()
    try:
        with transaction.atomic():
            account.save()
    except (IntegrityError, ValidationError, TypeError, ValueError) as error:
        found = model._default_manager.filter(
            **{model.USERNAME_FIELD: username}).first()
        if found is not None:  # created meanwhile by another process
            return found
        raise ValueError(
            'add_log(system=True) could not create the account %r (%s): '
            'create it, or name an existing one with '
            'GT_HISTORY_SYSTEM_USERNAME.' % (username, error)) from error
    return account


def _resolve_log_user(user):
    """Return the user a log entry should be attributed to.

    ``LogEntry.user`` is a NOT NULL foreign key, so an anonymous or missing
    user cannot be written directly.  Flows without an authenticated user
    (public registration, self sign-up) attribute the entry to the sentinel
    account named by ``GT_HISTORY_ANONYMOUS_USERNAME``.
    """
    if user is not None and getattr(user, 'is_authenticated', False):
        return user
    username = getattr(settings, 'GT_HISTORY_ANONYMOUS_USERNAME', None)
    if not username:
        raise ValueError(
            'add_log() needs an authenticated user, or the '
            'GT_HISTORY_ANONYMOUS_USERNAME setting naming the account that '
            'anonymous actions are attributed to.'
        )
    sentinel = get_user_model().objects.filter(username=username).first()
    if sentinel is None:
        raise ValueError(
            'GT_HISTORY_ANONYMOUS_USERNAME points at %r but no such user '
            'exists.' % username
        )
    return sentinel


def _save_relations(log_entry, related_objects, extra):
    """Store the HistoryRelation rows of one log entry.

    ``related_objects`` may be a single instance, an iterable of instances,
    or an iterable of ``(instance, data_dict)`` pairs.  Integers or strings
    are rejected on purpose: a bare pk does not say which model it belongs
    to, and guessing is how audit trails end up pointing at the wrong table.
    """
    # Circular import: djgentelella.models imports this module.
    from djgentelella.models import HistoryRelation  # noqa: PLC0415

    rows = []
    if related_objects is not None:
        if not hasattr(related_objects, '__iter__'):
            related_objects = [related_objects]
        for item in related_objects:
            data = None
            if isinstance(item, (tuple, list)):
                item, data = item
            if item is None:
                continue
            if isinstance(item, (int, str)):
                raise ValueError(
                    'related_objects takes model instances, not %r: a bare '
                    'pk does not identify the model it belongs to.' % item
                )
            rows.append(
                HistoryRelation(
                    log_entry=log_entry,
                    content_type=ContentType.objects.get_for_model(
                        item.__class__
                    ),
                    object_id=item.pk,
                    data=data,
                )
            )
    if extra:
        rows.append(HistoryRelation(log_entry=log_entry, data=extra))
    if rows:
        HistoryRelation.objects.bulk_create(rows)


def add_log(
    user,
    object,
    action_flag,
    model_name=None,
    changed_data=None,
    object_repr='',
    change_message='',
    content_type=None,
    related_objects=None,
    extra=None,
    *,
    system=False,
    actor='',
):
    """Write one audit entry and return the created ``LogEntry``.

    ``related_objects`` links the entry to other instances (one
    ``HistoryRelation`` row per instance, optionally ``(instance, data)``
    pairs), and ``extra`` stores an arbitrary dict as a relation row with no
    target — both queryable through ``LogEntry.gt_relations``.

    ``action_flag`` is one of :data:`ACTIONS`: Django's, ``HARD_DELETION``,
    ``RESTORE``, ``SECRET_READ`` or one added with :func:`register_action`.

    ``system=True`` records an event of the system -- a job, a command, a
    migration -- with no user: ``user`` must be ``None``, the entry goes to
    :func:`system_user` and ``extra`` gets ``{"gt_system": true,
    "gt_actor": actor}`` (``actor``: what did it, ``'rotate_credentials'``),
    so ``?extra={"gt_system": true}`` finds them. Without the flag a missing
    user is refused, or goes to ``GT_HISTORY_ANONYMOUS_USERNAME``, as before.
    """
    if system:
        if user is not None:
            raise ValueError('add_log(system=True) records an event without a '
                             'user: pass user=None (got %r)' % (user,))
        user = system_user()
        extra = dict(extra or {})
        extra[SYSTEM_KEY] = True
        extra[ACTOR_KEY] = str(actor or '')
    else:
        user = _resolve_log_user(user)

    if content_type is None:
        content_type = ContentType.objects.get_for_model(object)

    if model_name is None:
        model_name = object._meta.verbose_name

    if not isinstance(action_flag, int):
        raise ValueError('action_flag must be an integer')

    action_label = str(ACTIONS.get(action_flag, action_flag))

    if not object_repr:
        object_repr = _('An object of model %(model)s has been %(action)s') % {
            'model': _(str(model_name).capitalize()),
            'action': action_label,
        }

    changed_data = changed_data or []

    if change_message:
        # A caller-provided message is never replaced; the list of changed
        # fields is only appended to it.
        if action_flag not in (DELETION, HARD_DELETION, RESTORE) and changed_data:
            verbose_changes = []
            for field_name in changed_data:
                try:
                    verbose_changes.append(
                        str(object._meta.get_field(field_name).verbose_name)
                    )
                except FieldDoesNotExist:
                    verbose_changes.append(field_name)

            change_message = _('%(msg)s. Fields: %(fields)s') % {
                'msg': change_message,
                'fields': ', '.join(verbose_changes),
            }
    else:
        change_message = _(
            'The record %(obj)s of model %(model)s has been %(action)s'
        ) % {
            'obj': str(object),
            'model': _(model_name),
            'action': action_label,
        }

    # Not LogEntry.objects.log_action()/log_actions(): the former is removed
    # in Django 6.0 and the latter recomputes object_repr from str(obj),
    # discarding the localized message built above.
    log_entry = LogEntry(
        user_id=user.id,
        content_type_id=content_type.id,
        # LogEntry.object_id is text, as in Django's own log_action().
        object_id=str(object.pk),
        object_repr=object_repr[:200],
        action_flag=action_flag,
        change_message=change_message,
    )
    log_entry.save()

    _save_relations(log_entry, related_objects, extra)

    return log_entry
