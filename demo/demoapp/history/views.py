from django.contrib.auth.decorators import login_required
from .forms import HistoryFilterForm
from django.shortcuts import render

def history_view(request):

    return render(
        request,
        "gentelella/history/history.html",
        context={
            "form": HistoryFilterForm(),
        }
    )
