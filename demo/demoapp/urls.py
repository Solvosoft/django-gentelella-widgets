from django.conf.urls import url
from django.urls import path, include

from demoapp.cruds import Personclass, Countryclass, MenuItemclass
from demoapp.views import create_notification_view, color_widget_view, select_sever_view
from .views import knobView
from . import people_group
pclss = Personclass()
countryclss = Countryclass()
menuclss = MenuItemclass()

urlpatterns = [
        path('selects', select_sever_view),
        path('create/notification', create_notification_view),
        url(r'^markitup/', include('markitup.urls')),
        path('knobwidget/testform', knobView, name="knobwidgets"),
        path('colorwidgets', color_widget_view, name="colorwidgets"),

        path('pgroup/', people_group.PeopleGroupList.as_view(), name='pgroup-list'),
        path('pgroup/create/', people_group.PeopleGroupAdd.as_view(), name='pgroup-add'),
        path('pgroup/<int:pk>/', people_group.PeopleGroupChange.as_view(), name='pgroup-edit'),


              ] + pclss.get_urls() + countryclss.get_urls() + menuclss.get_urls()