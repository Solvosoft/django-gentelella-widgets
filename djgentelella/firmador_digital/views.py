from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.translation import gettext_lazy as _

from djgentelella.firmador_digital.forms import SignatureConfigForm
from djgentelella.firmador_digital.models import UserSignatureConfig

@login_required
def update_signature_settings(request):

    config, is_created = UserSignatureConfig.objects.get_or_create(user=request.user)


    if request.method == "POST":
        form = SignatureConfigForm(request.POST, instance=config, render_type="as_grid")
        if form.is_valid():
            form.save()
            messages.success(request, _("Updated signature settings successfully."))
            return redirect("signature_config")
    else:
        form = SignatureConfigForm(instance=config, render_type="as_grid")


    return render(
        request,
        "gentelella/digital_signature/update_signature_settings.html",
        context={
            "form": form
        }
    )
