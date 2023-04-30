from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def datatableViewExample(response):
    return render(response, 'gentelella/datatables/datatables.html')


@login_required(login_url='/accounts/login/')
def notification_datable_view(request):
    return render(request, 'gentelella/datatables/notification_datatables.html')
