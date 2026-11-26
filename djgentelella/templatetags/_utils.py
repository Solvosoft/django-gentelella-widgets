from djgentelella.menu import get_menu_widget as menu_widget_class
from djgentelella.menu import item_url


def get_title(item):
    """The title of a menu item in the active language (C20)."""
    if item.only_icon:
        return ''
    translated = getattr(item, 'translated_title', None)
    return translated() if translated is not None else item.title


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
