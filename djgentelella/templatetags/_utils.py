from django.utils.module_loading import import_string

from djgentelella.menu import item_url


def extract_element(item, context):
    fields = item.split('.')
    obj = context
    for field in fields:
        if hasattr(obj, field):
            obj = getattr(obj, field)
            if callable(obj):
                obj = obj()
        else:
            obj = None
            break
    if obj != context:
        return obj
    return None


def get_item_from_context(item, context):
    item = item.strip()
    if item.startswith('"') and item.endswith('"'):
        item = item[1:-1]
        return item
    if '.' in item:
        return extract_element(item, context)
    return item


def get_title(item):
    if item.only_icon:
        return ''
    return item.title


def extract_args(item, context):
    if item.reversed_args:
        args = [get_item_from_context(it, context) for it in
                item.reversed_args.split(',')]
        return args
    return None


def get_item_from_context_kwargs(item, context):
    key, value = item.split(':')
    key, value = key.strip(), get_item_from_context(value, context)
    return (key, value)


def extract_kwargs(item, context):
    if item.reversed_kwargs:
        kwargs = dict([get_item_from_context_kwargs(it, context) for it in
                       item.reversed_kwargs.split(',')])
        return kwargs
    return None


def get_link(item, context):
    """The link of ``item`` in a menu environment (``{'context': ...}``):
    :func:`djgentelella.menu.item_url` with its template context."""
    return item_url(item, context['context'])


def get_menu_widget(item, context):
    widget = import_string(item.strip())
    widget = widget(context)
    return widget
