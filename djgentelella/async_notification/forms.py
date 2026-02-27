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


class EmailNotificationForm(GTForm, forms.ModelForm):
    class Meta:
        model = EmailNotification
        fields = ('subject', 'message', 'recipients', 'bcc', 'cc',
                  'enqueued', 'send_individually')
        widgets = {
            'subject': genwidgets.TextInput,
            'message': EditorTinymce,
            'recipients': genwidgets.TextInput(
                attrs={'placeholder': _('Comma-separated emails or groups')}),
            'bcc': genwidgets.TextInput(
                attrs={'placeholder': _('BCC addresses')}),
            'cc': genwidgets.TextInput(
                attrs={'placeholder': _('CC addresses')}),
            'enqueued': genwidgets.YesNoInput,
            'send_individually': genwidgets.YesNoInput,
        }


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


class NewsLetterTemplateForm(GTForm, forms.ModelForm):
    class Meta:
        model = NewsLetterTemplate
        fields = ('title', 'slug', 'message', 'model_base')
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


class NewsLetterForm(GTForm, forms.ModelForm):
    class Meta:
        model = NewsLetter
        fields = ('template', 'subject', 'message', 'recipients',
                  'bcc', 'cc', 'attached_file')
        widgets = {
            'template': AutocompleteSelect('newslettertemplatebasename'),
            'subject': genwidgets.TextInput,
            'message': EditorTinymce,
            'recipients': genwidgets.TextInput(
                attrs={'placeholder': _('Comma-separated emails or groups')}),
            'bcc': genwidgets.TextInput(
                attrs={'placeholder': _('BCC addresses')}),
            'cc': genwidgets.TextInput(
                attrs={'placeholder': _('CC addresses')}),
        }


class NewsLetterTaskForm(GTForm, forms.ModelForm):
    class Meta:
        model = NewsLetterTask
        fields = ('newsletter', 'send_date')
        widgets = {
            'newsletter': AutocompleteSelect('newsletterbasename'),
            'send_date': genwidgets.DateTimeInput,
        }
