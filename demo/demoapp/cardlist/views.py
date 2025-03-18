from django.shortcuts import render
# CardTable
def cardListViewExample(response):
    return render(response, 'gentelella/cardlist/cardList.html')
