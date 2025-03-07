from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .forms import DigitalSignatureForm

@login_required
def digital_signature_view(request):

    return render(
        request,
        'gentelella/digital_signature/digital_signature.html',
        context={
            'form': DigitalSignatureForm(prefix='update'),
            'user': request.user,
        }
    )

