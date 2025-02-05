from django.shortcuts import render




def digital_signature_view(request):

    return render(request, 'gentelella/digital_signature/digital_signature.html')
