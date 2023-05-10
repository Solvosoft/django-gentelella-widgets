from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required(login_url='/accounts/login/')
def notification_datable_view(request):
    return render(request, 'gentelella/datatables/notification_datatables.html')
