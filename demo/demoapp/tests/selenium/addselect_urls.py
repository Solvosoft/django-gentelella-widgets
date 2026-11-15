"""Test-only urlconf: one form with every widget that has an "add" button.

No demo page has a tree with an add button, so the add-permission tests swap
in this urlconf with ``override_settings(ROOT_URLCONF=...)``, as
``layouts_urls`` does. ``?can_add=0`` renders the form as for a user without
``add_perms``.
"""

from django import forms
from django.http import HttpResponse, JsonResponse
from django.template import Context, Template
from django.urls import include, path, reverse_lazy

from demo.urls import urlpatterns as demo_urlpatterns
from djgentelella.forms.forms import GTForm, UserBoundWidgetsMixin
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets.trees import TreeSelectWithAdd

CHOICES = [('a', 'A'), ('b', 'B')]
ADD = {'add_url': reverse_lazy('addselect-create')}

PAGE = Template("""
{% extends 'gentelella/base.html' %}
{% block content %}<form method="post" id="the-form">{{ form.as_plain }}</form>
{% endblock %}
""")


class AddDemoForm(UserBoundWidgetsMixin, GTForm, forms.Form):
    plain = forms.ChoiceField(choices=CHOICES, widget=genwidgets.SelectWithAdd(
        attrs=dict(ADD), add_perms='auth.add_group'))
    tree = forms.ChoiceField(choices=CHOICES, widget=TreeSelectWithAdd(
        attrs=dict(ADD), add_perms='auth.add_group'))


def page_view(request):
    form = AddDemoForm(user=request.user)
    if request.GET.get('can_add') == '0':
        for field in form.fields.values():
            field.widget.can_add = False
    return HttpResponse(PAGE.render(Context({
        'form': form, 'request': request, 'user': request.user})))


def create_view(request):
    return JsonResponse({'ok': True, 'title': 'New entry',
                         'message': '<form><p id="add-form-body">the form</p></form>'})


urlpatterns = [
    path('addselect/', page_view, name='addselect-page'),
    path('addselect/create/', create_view, name='addselect-create'),
    path('', include(demo_urlpatterns)),
]
