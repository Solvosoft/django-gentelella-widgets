from django.shortcuts import render


def cleanable_fileinput_view(request):
    return render(request,

                  'gentelella/cleanable_fileinput/cleanable_fileinput.html'
                  )
