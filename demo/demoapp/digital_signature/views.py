from django.shortcuts import render
from .forms import DigitalSignatureForm




def digital_signature_view(request):


    return render(
        request,
        'gentelella/digital_signature/digital_signature.html',
        context={
            'form': DigitalSignatureForm(prefix='update'),
        }
    )
