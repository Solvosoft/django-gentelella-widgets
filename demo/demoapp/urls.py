from django.urls import path

from demoapp.cruds import Personclass, Countryclass, MenuItemclass
from demoapp.views import create_notification_view
from .views import knobView

pclss = Personclass()
countryclss = Countryclass()
menuclss = MenuItemclass()

urlpatterns = [
        path('create/notification', create_notification_view),
        path('knobwidget/testform', knobView, name="knobwidgets"),

              ] + pclss.get_urls() + countryclss.get_urls() + menuclss.get_urls()