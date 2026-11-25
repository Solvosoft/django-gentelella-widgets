import re
from urllib.parse import urlsplit

from django import forms
from django.utils.translation import gettext_lazy as _

from djgentelella.forms.forms import GTForm
from djgentelella.models import Feedback
from djgentelella.widgets import core as genwidgets

#: The longest comment accepted.
MAX_TEXT = 5000
_PAGE = re.compile(r'^[\w./-]{1,200}$')
_CONTROL = re.compile(r'[\x00-\x1f\x7f]')


class FeedbackForm(GTForm, forms.ModelForm):
    """What the feedback button sends. ``url``, ``page`` and ``browser`` are
    filled by the page's script when the user leaves those boxes ticked, and
    cleaned here: a path of this site without its query string, a design
    page slug and a line of text."""

    url = forms.CharField(required=False, widget=forms.HiddenInput)
    page = forms.CharField(required=False, widget=forms.HiddenInput)
    browser = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Feedback
        fields = ['kind', 'text', 'url', 'page', 'browser']
        widgets = {
            # A plain select: select2 inside a modal needs its dropdownParent.
            'kind': forms.Select(attrs={'class': 'form-select'}),
            'text': genwidgets.Textarea(attrs={'rows': 4, 'maxlength': MAX_TEXT}),
        }

    def clean_text(self):
        text = self.cleaned_data['text'].strip()
        if not text:
            raise forms.ValidationError(_('Write a comment.'))
        if len(text) > MAX_TEXT:
            raise forms.ValidationError(_('%(max)d characters at most.')
                                        % {'max': MAX_TEXT})
        return text

    def clean_url(self):
        value = (self.cleaned_data.get('url') or '').strip()
        parts = urlsplit(value)
        if not value or parts.scheme or parts.netloc or not parts.path.startswith('/') \
                or parts.path.startswith('//'):
            return ''
        return _CONTROL.sub('', parts.path)[:500]

    def clean_page(self):
        value = (self.cleaned_data.get('page') or '').strip()
        return value if _PAGE.match(value) else ''

    def clean_browser(self):
        return _CONTROL.sub(' ', self.cleaned_data.get('browser') or '').strip()[:500]


class ResponseForm(GTForm, forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['status', 'response']
        widgets = {
            'status': genwidgets.Select,
            'response': genwidgets.Textarea(attrs={'rows': 4}),
        }
