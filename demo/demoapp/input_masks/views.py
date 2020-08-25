from django.shortcuts import render
from .forms import InputMaskForm


def inputmasks(request):
    form=InputMaskForm()
    return render(request,'gentelella/input_masks/inputs.html', {'form': form})

