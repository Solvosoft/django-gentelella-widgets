"""Conditions, authorizations and feature flags in templates.

::

    {% load gtauthorization %}
    {% if_condition report.condition %}...{% else %}...{% endif_condition %}
    {% if_condition '{"perm": "ventas.view_pedido"}' %}...{% endif_condition %}
    {% if_flag "beta_reportes" %}...{% endif_flag %}
    {% if request|authorized:"es_supervisor" %}...{% endif %}
    {% authorized_for "es_dueno" pedido as puede %}

Every one needs ``request`` in the context; without it the user is anonymous
and the scope is global.
"""

from django import template

from djgentelella.authorization import (
    check_authorization,
    evaluate_condition,
    flag_enabled,
    parse_condition,
)

register = template.Library()


class ConditionalNode(template.Node):
    def __init__(self, test, args, nodelist_true, nodelist_false):
        self.test = test
        self.args = args
        self.nodelist_true = nodelist_true
        self.nodelist_false = nodelist_false

    def render(self, context):
        values = [arg.resolve(context) for arg in self.args]
        if self.test(context.get('request'), *values):
            return self.nodelist_true.render(context)
        return self.nodelist_false.render(context)


def _condition_holds(request, cond, obj=None):
    return evaluate_condition(parse_condition(cond), request, obj)


def _flag_on(request, name):
    try:
        return flag_enabled(name, request)
    except ValueError:  # not a flag name: off
        return False


def _block_tag(name, test, min_args, max_args):
    end = 'end' + name

    def compile_tag(parser, token):
        bits = token.split_contents()
        if not min_args <= len(bits) - 1 <= max_args:
            raise template.TemplateSyntaxError(
                '%r takes %s argument(s).' % (bits[0], min_args if min_args == max_args
                                              else '%d to %d' % (min_args, max_args)))
        args = [parser.compile_filter(bit) for bit in bits[1:]]
        nodelist_true = parser.parse(('else', end))
        token = parser.next_token()
        if token.contents == 'else':
            nodelist_false = parser.parse((end,))
            parser.delete_first_token()
        else:
            nodelist_false = template.NodeList()
        return ConditionalNode(test, args, nodelist_true, nodelist_false)
    register.tag(name, compile_tag)


#: ``{% if_condition cond [obj] %}``: ``cond`` is a dict or its JSON text.
_block_tag('if_condition', _condition_holds, 1, 2)
#: ``{% if_flag name %}``.
_block_tag('if_flag', _flag_on, 1, 1)


@register.filter
def authorized(request, name):
    """``request|authorized:"name"``: whether that authorization holds."""
    return check_authorization(name, request)


@register.simple_tag(takes_context=True)
def authorized_for(context, name, obj=None):
    """``{% authorized_for "name" obj as ok %}``: the authorization for ``obj``."""
    return check_authorization(name, context.get('request'), obj)


@register.simple_tag(takes_context=True)
def condition_holds(context, cond, obj=None):
    """``{% condition_holds cond obj as ok %}``."""
    return _condition_holds(context.get('request'), cond, obj)


@register.simple_tag(takes_context=True)
def flag_on(context, name):
    """``{% flag_on "name" as on %}``."""
    return _flag_on(context.get('request'), name)
