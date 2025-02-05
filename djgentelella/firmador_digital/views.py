from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from djgentelella.firmador_digital.forms import CardForm


@login_required
def digital_signature_view(request, pk):
    return render(request,
                  "gentelella/firmador_digital/firmador_digital.html",
                  context={
                      "pk": pk,
                      "form": CardForm(prefix="card", render_type="as_p"),
                      "permission": True
                  })
