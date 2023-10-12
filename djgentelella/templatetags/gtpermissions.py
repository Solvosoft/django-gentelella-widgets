from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def any_permission_required(context, *args, **kwargs):
    """
    This template tag check if the user have any permission in the list of perms
    """
    perms = args
    user = context['request'].user
    if not user.is_authenticated:
        return False
    for perm in perms:
        if user.has_perm(perm):
            return True
    return False


@register.simple_tag(takes_context=True)
def all_permission_required(context, *args, **kwargs):
    """
    This template tag check if the user have all permissions in the list of perms
    """

    perms = args
    user = context['request'].user
    if user.has_perms(perms):
        return True
    return False
