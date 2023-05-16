from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def notification_list_view(request):
    return render(request, 'gentelella/menu/notification_list.html')
