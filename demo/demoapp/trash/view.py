
from django.shortcuts import render
from demoapp.trash.form import CustomerForm


def trash_view(request):

    return render(
        request,
        "gentelella/trash/trash.html",
        context={
            "form_create": CustomerForm(prefix="create"),
            "form_update": CustomerForm(prefix="update"),
        }

    )
