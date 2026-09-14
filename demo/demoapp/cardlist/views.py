from django.shortcuts import render

from .forms import CardListPersonForm


# CardTable
def cardListViewExample(response):
    context = {
        'create_form': CardListPersonForm(prefix='create'),
        'update_form': CardListPersonForm(prefix='update'),
    }
    return render(response, 'gentelella/cardlist/cardList.html', context)
