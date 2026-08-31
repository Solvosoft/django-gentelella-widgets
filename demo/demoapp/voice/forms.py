from django import forms
from django.urls import reverse_lazy

from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets import tinymce as tinymce_widget

URL = reverse_lazy('voice-transcribe')


class VoiceTextareaForm(GTForm, forms.Form):
    """Same textarea widget in each of the three dictation modes."""
    segments = forms.CharField(
        label='Textarea — modo segments (por defecto, en vivo)',
        required=False,
        widget=genwidgets.VoiceDictation(url=URL, language='es'),
    )
    single = forms.CharField(
        label='Textarea — modo single (todo al parar)',
        required=False,
        widget=genwidgets.VoiceDictation(
            url=URL, language='es', attrs={'data-mode': 'single'}),
    )
    hybrid = forms.CharField(
        label='Textarea — modo hybrid (segmentos + reescritura final)',
        required=False,
        widget=genwidgets.VoiceDictation(
            url=URL, language='es', attrs={'data-mode': 'hybrid'}),
    )


class VoiceWysiwygForm(GTForm, forms.Form):
    """TinyMCE editor with the in-toolbar microphone button (segments mode)."""
    content = forms.CharField(
        label='TinyMCE — modo segments',
        required=False,
        widget=tinymce_widget.VoiceEditorTinymce(url=URL, language='es'),
    )
