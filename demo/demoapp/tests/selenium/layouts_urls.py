"""Test-only urlconf that renders one form through all four GTForm layouts.

``as_grid`` needs a ``grid_representation`` and no demo page defines one, so
there is nothing in the demo to point a browser at. Rather than add a page to
the demo just to test it, the layout tests swap in this urlconf with
``override_settings(ROOT_URLCONF=...)``; the live server picks it up and the
demo stays untouched.
"""

from django import forms
from django.http import HttpResponse
from django.urls import include, path
from django.template import Context, Template

from demo.urls import urlpatterns as demo_urlpatterns
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets

LAYOUTS = ('as_plain', 'as_inline', 'as_horizontal', 'as_grid')

PAGE = Template("""
{% extends 'gentelella/base.html' %}
{% block content %}
<div id="layout-{{ layout }}">
  <form method="post" id="the-form">{{ rendered }}</form>
</div>
{% endblock %}
""")


class LayoutDemoForm(GTForm, forms.Form):
    """Four fields, arranged in two rows of two columns for the grid case."""

    name = forms.CharField(widget=genwidgets.TextInput)
    email = forms.EmailField(widget=genwidgets.EmailInput)
    age = forms.IntegerField(widget=genwidgets.NumberInput)
    city = forms.CharField(widget=genwidgets.TextInput)

    grid_representation = [
        [['name'], ['email']],
        [['age'], ['city']],
    ]


def layout_view(request, layout):
    if layout not in LAYOUTS:
        return HttpResponse(status=404)
    form = LayoutDemoForm(render_type=layout)
    rendered = getattr(form, layout)()
    return HttpResponse(PAGE.render(Context({
        'layout': layout, 'rendered': rendered, 'request': request,
        'user': request.user,
    })))


urlpatterns = [
    path('layouts/<str:layout>/', layout_view, name='layout-demo'),
    path('', include(demo_urlpatterns)),
]
