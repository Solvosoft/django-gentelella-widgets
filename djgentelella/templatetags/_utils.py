from djgentelella.menu import get_menu_widget as menu_widget_class
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
    """The title of a menu item in the active language (C20)."""
    if item.only_icon:
        return ''
    translated = getattr(item, 'translated_title', None)
    return translated() if translated is not None else item.title


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
    """The menu widget the ``url_name`` ``item`` names, built with
    ``context``; ``None`` when the project does not declare it
    (:func:`djgentelella.menu.get_menu_widget`): it is never imported."""
    widget = menu_widget_class(item)
    if widget is None:
        return None
    return widget(context)
