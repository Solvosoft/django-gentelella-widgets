from django.urls import path

from demoapp.cruds import Personclass

pclss = Personclass()

urlpatterns = [

] + pclss.get_urls()