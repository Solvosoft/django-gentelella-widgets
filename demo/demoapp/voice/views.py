from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView

from .forms import VoiceTextareaForm, VoiceWysiwygForm


@method_decorator(ensure_csrf_cookie, name='dispatch')
class VoiceDemoView(TemplateView):
    template_name = 'gentelella/voice/inputs.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['textarea_form'] = VoiceTextareaForm()
        context['wysiwyg_form'] = VoiceWysiwygForm()
        return context
