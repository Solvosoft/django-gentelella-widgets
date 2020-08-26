from django.shortcuts import render
from .forms import InputMaskForms


def Create(request):
    form=InputMaskForms()
    return render(request,'gentelella/input_mask/inputs.html', {'form':form})