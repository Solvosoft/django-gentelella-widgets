from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from demoapp.formwidgets.forms import WidgetShowcaseForm
from demoapp.models import WidgetShowcase


@login_required
def form_widgets_view(request, pk=None):
    instance = get_object_or_404(WidgetShowcase, pk=pk) if pk else None
    form = WidgetShowcaseForm(instance=instance)
    if request.method == 'POST':
        form = WidgetShowcaseForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            return redirect(reverse('formwidgets'))
    return render(request, 'formwidgets.html', {
        'form': form, 'instance': instance,
        'items': WidgetShowcase.objects.order_by('-pk')[:20],
    })
