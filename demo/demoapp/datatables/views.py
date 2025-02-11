from django.shortcuts import render


def datatableViewExample(response):
    return render(response, 'gentelella/datatables/datatables.html')

