"""Components the designs tests register: none of them ships with djgentelella."""

from dataclasses import dataclass

from django.utils.html import format_html
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from djgentelella.designs.builtin import HtmlComponent
from djgentelella.designs.components import Endpoint, NodeBuild, RuntimeComponent


@dataclass
class EchoBuild(NodeBuild):
    message: str = ''


class EchoViewSet(viewsets.ViewSet):
    """Answers with what it can see of the design it serves."""

    permission_classes = [AllowAny]

    def list(self, request):
        build = request.gtdesign_build
        return Response({'node': build.id, 'message': build.message,
                         'page': request.gtdesign_page.pk})

    def retrieve(self, request, pk=None):
        return Response({'node': request.gtdesign_build.id, 'pk': pk})


class ShoutViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        return Response({'shout': request.gtdesign_build.message.upper()})


class EchoComponent(RuntimeComponent):
    """A node with endpoints: ``''`` (list and detail) and ``shout``."""

    type = 'echo'
    label = 'Echo'
    props_schema = {
        'type': 'object',
        'required': ['message'],
        'additionalProperties': False,
        'properties': {'message': {'type': 'string', 'minLength': 1}},
    }

    def resolve(self, node, rctx, path):
        return EchoBuild(node['id'], node['type'], dict(node['props']),
                         message=node['props']['message'])

    def render(self, build, rctx, children):
        return format_html('<p class="echo" data-gtdesign="{}">{}</p>',
                           build.id, build.message)

    def media(self, build, rctx):
        return {'js': ['gentelella/js/echo.js', '/static/shared.js'],
                'css': ['https://cdn.example.com/echo.css'],
                'inline_js': 'window.echo_%s = true;' % build.id}

    def endpoints(self, build):
        return [Endpoint('', EchoViewSet, 'echo-%s' % build.id),
                Endpoint('shout', ShoutViewSet, 'echo-shout-%s' % build.id)]


class FormComponent(RuntimeComponent):
    """Renders ``forms[props.form]`` of the design, to test the forms."""

    type = 'test_form'
    props_schema = {'type': 'object', 'required': ['form'],
                    'properties': {'form': {'type': 'string'}}}

    def resolve(self, node, rctx, path):
        build = NodeBuild(node['id'], node['type'], dict(node['props']))
        build.form = rctx.form(node['props']['form'], path + '.props.form')
        return build

    def render(self, build, rctx, children):
        form = build.form.get_form(prefix=build.id, preview=rctx.preview)
        return format_html('<form>{}</form>', form.as_plain())


class LoudHtml(HtmlComponent):
    """Replaces the built-in ``html`` through GT_DESIGN_COMPONENTS."""

    def render(self, build, rctx, children):
        return format_html('<div class="loud">{}</div>',
                           super().render(build, rctx, children))


class Discovered(RuntimeComponent):
    type = 'discovered'
