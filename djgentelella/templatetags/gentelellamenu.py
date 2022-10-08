from django import template

from django.utils.html import format_html
from django.utils.safestring import mark_safe

from djgentelella.models import MenuItem
from djgentelella.templatetags._utils import get_title, get_link, get_menu_widget

def update_widget_list(context, widget_list):
    if widget_list:
        if hasattr(context['request'], 'widget_list'):
            context['request'].widget_list += widget_list
        else:
            setattr(context['request'], 'widget_list',  widget_list)
def validate_menu_item(item, context):
    user = context['context']['request'].user
    if not item.permission.exists():
        return item
    perms=["%s.%s"%(i.content_type.app_label, i.codename) for i in item.permission.all()]
    if user.has_perms(perms):
        return item



def render_item(item, env={}, widget_list=[], level=0, ariabylabel=''):
    item = validate_menu_item(item, env)
    if not item:
        return ""

    children = item.children.exists()
    dropdown = "nav-item dropdown"
    a_class=""
    icon=""
    if level > 0:

        dropdown = "dropdown-submenu pull-left"
        if not children:
            dropdown = ""
    dev = '<li id="i_%d" role="presentation" class="%s imenu%d"  >'%(item.pk, dropdown, item.pk)

    if item.icon:
        icon = format_html('<i class="{}"></i>', item.icon)
    if children and level == 0:
        a_class = 'class="dropdown-toggle" data-bs-toggle="dropdown" role="button" aria-haspopup="true" aria-expanded="false"'
    else:
        a_class = 'tabindex = "-1"'

    if item.is_widget:
        wdcontext = {'id': 'tm_'+str(item.id), 'item': item}
        wdcontext.update(env)
        widget = get_menu_widget(item.url_name, context=wdcontext)
        dev += widget.render()
        widget_list.append(widget)

    else:
        dev += format_html("""<a id="{}" href="{}" title="{}" %s >{} {} </a> """%a_class,
                      'tm_'+str(item.id), get_link(item, env),get_title(item), icon, get_title(item))
    ariabylabel = 'tm_'+str(item.id)
    children = item.children.exists()

    if children:
        dev += '<ul class="dropdown-menu " id="m_%d"  aria-labelledby="%s" role="menu">' % (
            item.pk, ariabylabel)
    for node in item.children.all():
        dev += render_item(node, env=env, level=level+1, widget_list=widget_list)
    if children:
        dev += '</ul>'
    dev += '</li>'

    return dev

register = template.Library()
@register.simple_tag(takes_context=True)
def top_menu(context,  *args, **kwargs):
    menues = MenuItem.objects.filter(parent_id=None, category='main').order_by('position')
    dev  = ''
    environment = {
        'context': context,
        'args': args,
        'kwargs': kwargs
    }
    widget_list = []
    for item in menues:
        dev += render_item(item, env=environment, widget_list=widget_list)
    update_widget_list(context, widget_list)
    return mark_safe(dev)



def render_sidebar_item(item, father_pos=0, level=0, env={}, widget_list=[]):
    item = validate_menu_item(item, env)
    if not item:
        return ""

    children, icon = item.children.exists(), ''
    if item.icon:
        icon = '<i class="%s"></i>'%item.icon
    # level 1
    if not level:
        dev = '<div id="%s" class ="menu_section" ><h3>%s %s</h3>'%(
            'sb'+str(item.id), icon, get_title(item))
    else:
        dev = '<li %s>'%('class="sub_menu"' if level == 2 else '' )
        dev += """<a id="%s" href="%s" >%s %s %s</a> """%(
            'sb'+str(item.id), get_link(item, env),  icon, get_title(item),
        '<span class="fa fa-chevron-down"></span>' if children else '')

    if children:
        dev += '<ul class="%s">' % ("nav side-menu" if not level and not father_pos else "nav child_menu")
        for i, node in enumerate(item.children.all()):
            dev += render_sidebar_item(node, i, env=env, level=level+1, widget_list=widget_list)
        dev += '</ul>'
    if not level:
        dev  += "</div>"
    else:
        dev += '</li>'
    return dev

@register.simple_tag(takes_context=True)
def sidebar_menu(context,  *args, **kwargs):
    menues = MenuItem.objects.filter(parent_id=None, category='sidebar').order_by('position')
    dev = ''
    environment = {
        'context': context,
        'args': args,
        'kwargs': kwargs
    }
    widget_list = []
    for item in menues:
        dev += render_sidebar_item(item, env=environment, widget_list=widget_list)
    update_widget_list(context, widget_list)
    return mark_safe(dev)



def render_footer_sidebar_item(item, env={}, widget_list=[]):
    item = validate_menu_item(item, env)
    if not item:
        return ""

    context = {
        'id': "fsb_"+str(item.id),

        'title': '',
        'link': '',
        'icon': ''
    }
    if item.is_widget:
        wdcontext = {'id': 'tm_'+str(item.id),  'item': item}
        wdcontext.update(env)
        widget= get_menu_widget(item.url_name, context=wdcontext)
        context.update({
            'title': widget.get_title(item) if hasattr(widget, 'get_title') else '',
            'link': widget.get_link(item, env) if hasattr(widget, 'get_link') else '#',
            'icon': widget.get_icon(item) if hasattr(widget, 'get_icon') else item.icon
        })
        widget_list.append(widget)
        if hasattr(widget, 'get_menu_item'):
            return widget.get_menu_item()


    else:
        context.update( {
            'title': get_title(item),
            'link': get_link(item, env),
            'icon': item.icon
        })

    return """
    <a id="%(id)s" title="%(title)s" href="%(link)s">
      <span class="%(icon)s" aria-hidden="true"></span>
    </a>
    """%context

@register.simple_tag(takes_context=True)
def footer_sidebar_menu(context,  *args, **kwargs):
    menues = MenuItem.objects.filter(parent_id=None, category='sidebarfooter').order_by('position')
    dev = ''
    environment = {
        'context': context,
        'args': args,
        'kwargs': kwargs
    }
    widget_list = []
    for item in menues:
        dev += render_footer_sidebar_item(item, env=environment, widget_list=widget_list)
    update_widget_list(context, widget_list)
    return mark_safe(dev)


@register.simple_tag(takes_context=True)
def render_external_widget(context,  *args, **kwargs):
    dev = ''
    if hasattr(context['request'], 'widget_list'):
        widget_list=context['request'].widget_list
        for widget in widget_list:
            if hasattr(widget, 'render_content'):
                dev += widget.render_content()
            else:
                dev += widget.render()
    return mark_safe(dev)

@register.simple_tag(takes_context=True)
def render_menu_js_widget(context,  *args, **kwargs):
    dev = ''
    if hasattr(context['request'], 'widget_list'):
        widget_list = context['request'].widget_list
        for widget in widget_list:
            if hasattr(widget, 'render_js'):
                dev += widget.render_js()
    return mark_safe(dev)

@register.simple_tag(takes_context=True)
def render_extra_html_menu(context,  *args, **kwargs):
    dev = ''
    if hasattr(context['request'], 'widget_list'):
        widget_list = context['request'].widget_list
        for widget in widget_list:
            if hasattr(widget, 'render_external_html'):
                dev += widget.render_external_html()
    return mark_safe(dev)