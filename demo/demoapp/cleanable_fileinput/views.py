from django.shortcuts import render

from demoapp.cleanable_fileinput.forms import CleanableFileInputForm


def cleanable_fileinput_view(request):
    return render(request,
                  'gentelella/cleanable_fileinput/cleanable_fileinput.html',
                  {
                      'form': CleanableFileInputForm(prefix='form')
                  }
                  )
