from django.conf import settings
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.utils.translation import gettext_lazy as _

HARD_DELETION = 4
RESTORE = 5

ACTIONS = {
    ADDITION: _('created'),
    CHANGE: _('updated'),
    DELETION: _('deleted'),
    HARD_DELETION: _('hard deleted'),
    RESTORE: _('restored'),
}


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
):
    """Write one audit entry and return the created ``LogEntry``.

    ``related_objects`` links the entry to other instances (one
    ``HistoryRelation`` row per instance, optionally ``(instance, data)``
    pairs), and ``extra`` stores an arbitrary dict as a relation row with no
    target — both queryable through ``LogEntry.gt_relations``.
    """
    user = _resolve_log_user(user)

    if content_type is None:
        content_type = ContentType.objects.get_for_model(object)

    if model_name is None:
        model_name = object._meta.verbose_name

    if not isinstance(action_flag, int):
        raise ValueError('action_flag must be an integer')

    action_label = ACTIONS.get(action_flag, str(action_flag))

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
        object_id=object.pk,
        object_repr=object_repr[:200],
        action_flag=action_flag,
        change_message=change_message,
    )
    log_entry.save()

    _save_relations(log_entry, related_objects, extra)

    return log_entry
