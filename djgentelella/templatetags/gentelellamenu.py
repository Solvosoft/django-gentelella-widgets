from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from djgentelella.models import MenuItem
from djgentelella.templatetags._utils import get_title, get_link


def render_item(item, env={}):
    children = item.children.exists()
    dropdown = "nav-item dropdown"
    a_class=""
    icon=""
    if item.level > 0:
        dropdown = "dropdown-submenu pull-left"
        if not children:
            dropdown =  ""
    dev = '<li id="i_%d" role="presentation" class="%s imenu%d" >'%(item.pk, dropdown, item.pk)

    if item.icon:
        icon = format_html('<i class="{}"></i>', item.icon)
    if children and item.level == 0:
        a_class = 'class="dropdown-toggle" data-toggle="dropdown" role="button" aria-haspopup="true" aria-expanded="false"'
    else:
        a_class = 'tabindex = "-1"'
    dev += format_html("""<a href="{}" %s >{} {} </a> """%a_class,
                      item.url_name,  icon, get_title(item) )
    for node in item.children.all():
        dev += '<ul class="dropdown-menu " id="m_%d_%d"  aria-labelledby="navbarDropdown" role="menu">'%(
            item.pk, node.pk)
        dev += render_item(node)
        dev += '</ul>'
    dev += '</li>'
    return dev

register = template.Library()
@register.simple_tag(takes_context=True)
def top_menu(context,  *args, **kwargs):
    menues = MenuItem.objects.filter(parent_id=None, category='main')
    dev  = ''
    environment = {
        'context': context,
        'args': args,
        'kwargs': kwargs
    }
    for item in menues:
        dev += render_item(item, env=environment)

    return mark_safe(dev)



def render_sidebar_item(item, father_pos=0, env={}):
    print("-"*item.level, item.title)
    children, icon = item.children.exists(), ''
    if item.icon:
        icon = '<i class="%s"></i>'%item.icon
    # level 1
    if not item.level:
        dev = '<div class ="menu_section" ><h3>%s %s</h3>'%(icon, get_title(item))
    else:
        dev = '<li %s>'%('class="sub_menu"' if item.level == 2 else '' )
        dev += """<a href="%s" >%s %s %s</a> """%( item.url_name,  icon, get_title(item),
        '<span class="fa fa-chevron-down"></span>' if children else '')

    if children:
        dev += '<ul class="%s">' % ("nav side-menu" if not item.level and not father_pos else "nav child_menu")
        for i, node in enumerate(item.children.all()):
            dev += render_sidebar_item(node, i)
        dev += '</ul>'
    if not item.level:
        dev  += "</div>"
    else:
        dev += '</li>'
    return dev

@register.simple_tag(takes_context=True)
def sidebar_menu(context,  *args, **kwargs):
    menues = MenuItem.objects.filter(parent_id=None, category='sidebar')
    dev = ''
    environment = {
        'context': context,
        'args': args,
        'kwargs': kwargs
    }

    for item in menues:
        dev += render_sidebar_item(item, env=environment)
    return mark_safe(dev)



def render_footer_sidebar_item(item, env={}):
    return """
    <a title="%s" href="%s">
      <span class="%s" aria-hidden="true"></span>
    </a>
    """%(
        get_title(item),
        get_link(item, env),
        item.icon
    )

@register.simple_tag(takes_context=True)
def footer_sidebar_menu(context,  *args, **kwargs):
    menues = MenuItem.objects.filter(parent_id=None, category='sidebarfooter')
    dev = ''
    environment = {
        'context': context,
        'args': args,
        'kwargs': kwargs
    }
    for item in menues:
        dev += render_footer_sidebar_item(item, env=environment)
    return mark_safe(dev)
