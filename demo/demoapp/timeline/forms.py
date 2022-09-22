from django import forms
from django.urls import reverse_lazy

from djgentelella.forms.forms import GTForm
from djgentelella.widgets.timeline import UrlTimeLineInput


class TimelineForm(GTForm, forms.Form):
    timeline = forms.CharField(widget=UrlTimeLineInput(
        attrs={"data-url": reverse_lazy('exampletimeline-list'), 'style': "height: 650px;",
        'frameborder':"0", "data-option_language": 'es'}))