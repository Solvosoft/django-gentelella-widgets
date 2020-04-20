from django.urls import path

from demoapp.cruds import Personclass, Countryclass, MenuItemclass

pclss = Personclass()
countryclss = Countryclass()
menuclss = MenuItemclass()

urlpatterns = [] + pclss.get_urls() + countryclss.get_urls() + menuclss.get_urls()