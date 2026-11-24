"""Querysets of form fields that would otherwise cost one query per option.

``str(permission)`` reads its content type, so a field listing ``Permission``
rows without ``select_related('content_type')`` runs one query per option
every time it is drawn -- hundreds on a menu item or a group form.
"""
from django.apps import apps

__all__ = ['optimize_form_querysets', 'permission_queryset']


def permission_queryset():
    """``Permission`` rows with their content types, ready to be listed."""
    return apps.get_model('auth', 'Permission').objects.select_related(
        'content_type')


def optimize_form_querysets(form):
    """Give each ``Permission`` choice field of ``form`` its content types.

    Only fields whose queryset selects no related model yet are touched, so a
    queryset a form built on purpose is kept.
    """
    permission = apps.get_model('auth', 'Permission')
    for field in form.fields.values():
        queryset = getattr(field, 'queryset', None)
        if (queryset is not None and queryset.model is permission
                and not queryset.query.select_related):
            field.queryset = queryset.select_related('content_type')
    return form
