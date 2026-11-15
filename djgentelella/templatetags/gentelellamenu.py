from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from djgentelella.authorization import evaluate_condition
from djgentelella.models import MenuItem
from djgentelella.sites import get_current_site, site_q
from djgentelella.templatetags._utils import get_title, get_link, get_menu_widget


# url_names that do not name a page: items that only open a dropdown, or
# point nowhere yet, share them. They are no identity on their own.
PLACEHOLDER_URL_NAMES = frozenset(('', '/', '#'))


def override_identity(item):
    """What a Site item must share with a global one to replace it.

    ``(url_name, category)``; when ``url_name`` is a placeholder (``''``,
    ``'/'``, ``'#'``) the ``title`` too, or one Site item with ``url_name='/'``
    would hide every global placeholder item of its level.
    """
    url_name = (item.url_name or '').strip()
    if url_name in PLACEHOLDER_URL_NAMES:
        return (url_name, item.category, item.title)
    return (url_name, item.category)


def scope_menu_items(queryset, site):
    """The items of ``queryset`` visible on ``site``, in their order.

    Global items (``site=NULL``) and the Site's own ones. ``queryset`` is one
    level of the tree -- the roots of a category or the children of an item --
    and on that level an item of the Site replaces the global one with the same
    :func:`override_identity`, children included.
    """
    items = list(queryset.filter(site_q(site)))
    if site is None:
        return items
    overridden = {override_identity(i) for i in items if i.site_id is not None}
    return [i for i in items
            if i.site_id is not None or override_identity(i) not in overridden]


def get_children(item, env):
    return scope_menu_items(item.children.all(), env.get('site'))


def get_roots(category, environment):
    return scope_menu_items(
        MenuItem.objects.filter(parent_id=None, category=category).order_by(
            'position'),
        environment['site'])


def menu_environment(context, args, kwargs):
    return {
        'context': context,
        'args': args,
        'kwargs': kwargs,
        'site': get_current_site(context.get('request')),
    }


def update_widget_list(context, widget_list):
    if widget_list:
        if hasattr(context['request'], 'widget_list'):
            context['request'].widget_list += widget_list
        else:
            setattr(context['request'], 'widget_list', widget_list)


def validate_menu_item(item, context):
    """``item`` if the user may see it, else ``None``: it needs all of its
    permissions *and* its condition (:mod:`djgentelella.authorization`),
    when it has them."""
    request = context['context']['request']
    user = request.user
    if item.permission.exists():
        perms = ['%s.%s' % (i.content_type.app_label, i.codename) for i in
                 item.permission.all()]
        if not user.has_perms(perms):
            return None
    if item.condition is not None and not evaluate_condition(item.condition,
                                                             request):
        return None
    return item


def render_item(item, env={}, widget_list=[], level=0, ariabylabel=''):
    item = validate_menu_item(item, env)
    if not item:
        return ''

    child_items = get_children(item, env)
    children = bool(child_items)
    dropdown = 'nav-item dropdown'
    a_class = ''
    icon = ''
    if level > 0:

        dropdown = 'dropdown-submenu pull-left'
        if not children:
            dropdown = ''
    dev = '<li id="i_%d" role="presentation" class="%s imenu%d"  >' % (
        item.pk, dropdown, item.pk)

    if item.icon:
        icon = format_html('<i class="{}"></i>', item.icon)
    if children and level == 0:
        # auto-close="outside": a click inside the menu opens a nested level
        # rather than closing the whole thing. Bootstrap's default closes on
        # any click, which shut the parent the instant a submenu was opened --
        # so the second and third levels could never be reached by clicking.
        a_class = 'class="dropdown-toggle" data-bs-toggle="dropdown" role="button" ' + \
                  ' data-bs-auto-close="outside"' + \
                  ' aria-haspopup="true" aria-expanded="false"'
    else:
        a_class = 'tabindex = "-1"'

    if item.is_widget:
        wdcontext = {'id': 'tm_' + str(item.id), 'item': item}
        wdcontext.update(env)
        widget = get_menu_widget(item.url_name, context=wdcontext)
        dev += widget.render()
        widget_list.append(widget)

    else:
        dev += format_html(
            """<a id="{}" href="{}" title="{}" %s >{} {} </a> """ % a_class,
            'tm_' + str(item.id), get_link(item, env), get_title(item), icon,
            get_title(item))
    ariabylabel = 'tm_' + str(item.id)

    if children:
        dev += '<ul class="dropdown-menu" id="m_%d" aria-labelledby="%s" role="menu">' \
               % (item.pk, ariabylabel)
    for node in child_items:
        dev += render_item(node, env=env, level=level + 1, widget_list=widget_list)
    if children:
        dev += '</ul>'
    dev += '</li>'

    return dev


register = template.Library()


@register.simple_tag(takes_context=True)
def top_menu(context, *args, **kwargs):
    environment = menu_environment(context, args, kwargs)
    menues = get_roots('main', environment)
    dev = ''
    widget_list = []
    for item in menues:
        dev += render_item(item, env=environment, widget_list=widget_list)
    update_widget_list(context, widget_list)
    return mark_safe(dev)


def render_sidebar_item(item, father_pos=0, level=0, env={}, widget_list=[]):
    item = validate_menu_item(item, env)
    if not item:
        return ''

    child_items = get_children(item, env)
    children, icon = bool(child_items), ''
    if item.icon:
        icon = format_html('<i class="{}"></i>', item.icon)
    # level 1. The title, link and icon come from the database: escaped.
    if not level:
        dev = format_html('<div id="{}" class ="menu_section" ><h3>{} {}</h3>',
                          'sb' + str(item.id), icon, get_title(item))
    else:
        dev = '<li %s>' % ('class="sub_menu"' if level == 2 else '')
        # An entry with children is a disclosure control, so it has to say so:
        # custom.js flips aria-expanded alongside the `active` class.
        dev += format_html(
            """<a id="{}" href="{}" {}>{} {} {}</a> """,
            'sb' + str(item.id), get_link(item, env),
            mark_safe('aria-expanded="false"') if children else '',
            icon, get_title(item),
            mark_safe('<span class="fa fa-chevron-down"></span>') if children else '')

    if children:
        dev += '<ul class="%s">' % (
            'nav side-menu' if not level and not father_pos else 'nav child_menu')
        for i, node in enumerate(child_items):
            dev += render_sidebar_item(node, i, env=env, level=level + 1,
                                       widget_list=widget_list)
        dev += '</ul>'
    if not level:
        dev += '</div>'
    else:
        dev += '</li>'
    return dev


@register.simple_tag(takes_context=True)
def sidebar_menu(context, *args, **kwargs):
    environment = menu_environment(context, args, kwargs)
    menues = get_roots('sidebar', environment)
    dev = ''
    widget_list = []
    for item in menues:
        dev += render_sidebar_item(item,
                                   env=environment,
                                   widget_list=widget_list)
    update_widget_list(context, widget_list)
    return mark_safe(dev)


def render_footer_sidebar_item(item, env={}, widget_list=[]):
    item = validate_menu_item(item, env)
    if not item:
        return ''

    context = {
        'id': 'fsb_' + str(item.id),

        'title': '',
        'link': '',
        'icon': ''
    }
    if item.is_widget:
        wdcontext = {'id': 'tm_' + str(item.id), 'item': item}
        wdcontext.update(env)
        widget = get_menu_widget(item.url_name, context=wdcontext)
        context.update({
            'title': widget.get_title(item) if hasattr(widget, 'get_title') else '',
            'link': widget.get_link(item, env) if hasattr(widget, 'get_link') else '#',
            'icon': widget.get_icon(item) if hasattr(widget, 'get_icon') else item.icon
        })
        widget_list.append(widget)
        if hasattr(widget, 'get_menu_item'):
            return widget.get_menu_item()

    else:
        context.update({
            'title': get_title(item),
            'link': get_link(item, env),
            'icon': item.icon
        })

    return format_html("""
    <a id="{id}" title="{title}" href="{link}">
      <span class="{icon}" aria-hidden="true"></span>
    </a>
    """, **context)


@register.simple_tag(takes_context=True)
def footer_sidebar_menu(context, *args, **kwargs):
    environment = menu_environment(context, args, kwargs)
    menues = get_roots('sidebarfooter', environment)
    dev = ''
    widget_list = []
    for item in menues:
        dev += render_footer_sidebar_item(item, env=environment,
                                          widget_list=widget_list)
    update_widget_list(context, widget_list)
    return mark_safe(dev)


@register.simple_tag(takes_context=True)
def render_external_widget(context, *args, **kwargs):
    dev = ''
    if hasattr(context['request'], 'widget_list'):
        widget_list = context['request'].widget_list
        for widget in widget_list:
            if hasattr(widget, 'render_content'):
                dev += widget.render_content()
            else:
                dev += widget.render()
    return mark_safe(dev)


@register.simple_tag(takes_context=True)
def render_menu_js_widget(context, *args, **kwargs):
    dev = ''
    if hasattr(context['request'], 'widget_list'):
        widget_list = context['request'].widget_list
        for widget in widget_list:
            if hasattr(widget, 'render_js'):
                dev += widget.render_js()
    return mark_safe(dev)


@register.simple_tag(takes_context=True)
def render_extra_html_menu(context, *args, **kwargs):
    dev = ''
    if hasattr(context['request'], 'widget_list'):
        widget_list = context['request'].widget_list
        for widget in widget_list:
            if hasattr(widget, 'render_external_html'):
                dev += widget.render_external_html()
    return mark_safe(dev)
