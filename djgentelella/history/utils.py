from django.utils.translation import gettext_lazy as _
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.contenttypes.models import ContentType

HARD_DELETION = 4
RESTORE = 5

ACTIONS = {
    ADDITION: _("created"),
    CHANGE: _("updated"),
    DELETION: _("deleted"),
    HARD_DELETION: _("hard deleted"),
    RESTORE: _("restored"),
}


def add_log(
    user,
    object,
    action_flag,
    model_name=None,
    changed_data=None,
    object_repr="",
    change_message="",
    content_type=None,
):
    if content_type is None:
        content_type = ContentType.objects.get_for_model(object)

    if model_name is None:
        model_name = object._meta.verbose_name

    if not isinstance(action_flag, int):
        raise ValueError("action_flag must be an integer")

    action_label = ACTIONS.get(action_flag, str(action_flag))

    if not object_repr:
        object_repr = _("An object of model %(model)s has been %(action)s") % {
            "model": _(str(model_name).capitalize()),
            "action": action_label,
        }

    changed_data = changed_data or []

    if change_message:
        if action_flag != DELETION and changed_data:
            verbose_changes = [
                str(object._meta.get_field(f).verbose_name)
                for f in changed_data
            ]

            change_message = _("%(msg)s. Fields: %(fields)s") % {
                "msg": change_message,
                "fields": ", ".join(verbose_changes),
            }
        else: # delete, restore, hard delete
            change_message = _("The record %(obj)s of model %(model)s has been %(action)s") % {
                "obj": str(object),
                "model": _(model_name),
                "action": action_label,
            }

    LogEntry.objects.log_action(
        user_id=user.id,
        content_type_id=content_type.id,
        object_id=object.pk,
        object_repr=object_repr,
        action_flag=action_flag,
        change_message=change_message,
    )

