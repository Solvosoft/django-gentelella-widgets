"""
Forms for the async_notification module.

All forms use GTForm for Bootstrap-compatible rendering and
djgentelella widgets.
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets.selects import AutocompleteSelect
from djgentelella.widgets.tinymce import EditorTinymce

from djgentelella.async_notification.models import (
    EmailNotification, EmailTemplate,
    NewsLetterTemplate, NewsLetter, NewsLetterTask
)
from djgentelella.async_notification.registry import get_all_contexts
from djgentelella.async_notification.settings import (
    ASYNC_NOTIFICATION_BASE_TEMPLATES, ASYNC_NEWS_BASE_MODELS
)


class EmailListField(forms.CharField):
    """CharField that maps a comma-separated string to a JSON list.

    Bridges the ``recipients``/``bcc``/``cc`` JSONField model columns to a
    friendly single-line text input.
    """

    def prepare_value(self, value):
        if isinstance(value, (list, tuple)):
            return ', '.join(value)
        return value

    def to_python(self, value):
        value = super().to_python(value)
        if not value:
            return []
        return [item.strip() for item in value.split(',') if item.strip()]


class EmailNotificationForm(GTForm, forms.ModelForm):
    recipients = EmailListField(
        required=False, widget=genwidgets.TextInput(
            attrs={'placeholder': _('Comma-separated emails or groups')}))
    bcc = EmailListField(
        required=False, widget=genwidgets.TextInput(
            attrs={'placeholder': _('BCC addresses')}))
    cc = EmailListField(
        required=False, widget=genwidgets.TextInput(
            attrs={'placeholder': _('CC addresses')}))

    class Meta:
        model = EmailNotification
        fields = ('subject', 'message', 'recipients', 'bcc', 'cc',
                  'base_template', 'enqueued', 'send_individually')
        widgets = {
            'subject': genwidgets.TextInput,
            'message': EditorTinymce,
            'enqueued': genwidgets.YesNoInput,
            'send_individually': genwidgets.YesNoInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['base_template'].widget = genwidgets.Select(
            choices=_base_template_choices())


class EmailTemplateForm(GTForm, forms.ModelForm):
    class Meta:
        model = EmailTemplate
        fields = ('code', 'subject', 'message', 'bcc', 'cc',
                  'context_code', 'base_template')
        widgets = {
            'code': genwidgets.TextInput,
            'subject': genwidgets.TextInput,
            'message': EditorTinymce,
            'bcc': genwidgets.TextInput(
                attrs={'placeholder': _('BCC addresses')}),
            'cc': genwidgets.TextInput(
                attrs={'placeholder': _('CC addresses')}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate context_code choices from registry
        contexts = get_all_contexts()
        context_choices = [('', '---------')]
        context_choices.extend(
            (code, code) for code in contexts.keys()
        )
        self.fields['context_code'].widget = genwidgets.Select(
            choices=context_choices)

        # Populate base_template choices from settings
        template_choices = [('', '---------')]
        template_choices.extend(
            (key, key) for key in ASYNC_NOTIFICATION_BASE_TEMPLATES.keys()
        )
        self.fields['base_template'].widget = genwidgets.Select(
            choices=template_choices)


def _base_template_choices():
    choices = [('', '---------')]
    choices.extend(
        (key, key) for key in ASYNC_NOTIFICATION_BASE_TEMPLATES.keys())
    return choices


class NewsLetterTemplateForm(GTForm, forms.ModelForm):
    class Meta:
        model = NewsLetterTemplate
        fields = ('title', 'slug', 'message', 'model_base', 'base_template')
        widgets = {
            'title': genwidgets.TextInput,
            'slug': genwidgets.TextInput,
            'message': EditorTinymce,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        model_choices = [('', '---------')]
        model_choices.extend(
            (key, key) for key in ASYNC_NEWS_BASE_MODELS.keys()
        )
        self.fields['model_base'].choices = model_choices
        self.fields['model_base'].widget = genwidgets.Select(
            choices=model_choices)
        self.fields['base_template'].widget = genwidgets.Select(
            choices=_base_template_choices())


class NewsLetterForm(GTForm, forms.ModelForm):
    recipients = EmailListField(
        required=False, widget=genwidgets.TextInput(
            attrs={'placeholder': _('Comma-separated emails or groups')}))
    bcc = EmailListField(
        required=False, widget=genwidgets.TextInput(
            attrs={'placeholder': _('BCC addresses')}))
    cc = EmailListField(
        required=False, widget=genwidgets.TextInput(
            attrs={'placeholder': _('CC addresses')}))

    class Meta:
        model = NewsLetter
        fields = ('template', 'subject', 'message', 'recipients',
                  'bcc', 'cc', 'base_template', 'attached_file',
                  'filters_querystring')
        widgets = {
            'template': AutocompleteSelect('newslettertemplatebasename'),
            'subject': genwidgets.TextInput,
            'message': EditorTinymce,
            'filters_querystring': forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['base_template'].widget = genwidgets.Select(
            choices=_base_template_choices())


class NewsLetterTaskForm(GTForm, forms.ModelForm):
    class Meta:
        model = NewsLetterTask
        fields = ('newsletter', 'send_date')
        widgets = {
            'newsletter': AutocompleteSelect('newsletterbasename'),
            'send_date': genwidgets.DateTimeInput,
        }
