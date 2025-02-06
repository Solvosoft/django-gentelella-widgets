from django.shortcuts import render


def datatableViewExample(response):
    return render(response, 'gentelella/datatables/datatables.html')

# CardTable
def cardtableViewExample(response):
    return render(response, 'gentelella/cardtables/cardtables.html')
