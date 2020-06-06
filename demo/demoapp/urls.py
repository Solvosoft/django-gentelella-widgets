from django.conf.urls import url
from django.urls import path, include

from demoapp.cruds import Personclass, Countryclass, MenuItemclass
from demoapp.views import create_notification_view

pclss = Personclass()
countryclss = Countryclass()
menuclss = MenuItemclass()

urlpatterns = [
        path('create/notification', create_notification_view),
        url(r'^markitup/', include('markitup.urls')),
              ] + pclss.get_urls() + countryclss.get_urls() + menuclss.get_urls()