"""
    This view requires an authenticated user session (enforced by the
    @login_required decorator) to ensure only authorized users can access
    the digital signature functionality.

    Usage notes:
    - Make sure 'DigitalSignatureForm' is defined in 'forms.py' and correctly
      includes the digital signature widget fields.
    - Add a corresponding URL pattern to 'urls.py',
"""

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
        }
    )

