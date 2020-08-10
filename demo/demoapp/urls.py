from django.conf.urls import url
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from demoapp.cruds import Personclass, Countryclass, MenuItemclass
from demoapp.views import create_notification_view, color_widget_view, person_reltable_view
from . import api
from .autocomplete import views as autocompleteviews
from .views import knobView

pclss = Personclass()
countryclss = Countryclass()
menuclss = MenuItemclass()

urlpatterns = [
        path('create/notification', create_notification_view),
        url(r'^markitup/', include('markitup.urls')),
        path('knobwidget/testform', knobView, name="knobwidgets"),
        path('colorwidgets', color_widget_view, name="colorwidgets"),
        path('pgroup/', autocompleteviews.PeopleGroupList.as_view(), name='pgroup-list'),
        path('pgroup/create/', autocompleteviews.PeopleGroupAdd.as_view(), name='pgroup-add'),
        path('pgroup/<int:pk>/', autocompleteviews.PeopleGroupChange.as_view(), name='pgroup-edit'),
        path('abcde/', autocompleteviews.ABCDEList.as_view(), name='abcde-list'),
        path('abcde/create/', autocompleteviews.ABCDECreate.as_view(), name='abcde-add'),
        path('abcde/<int:pk>/', autocompleteviews.ABCDEChange.as_view(), name='abcde-edit'),
        path('datables/', person_reltable_view, name='abcde-edit'),
] + pclss.get_urls() + countryclss.get_urls() + menuclss.get_urls()

router = DefaultRouter()
router.register('persontable', api.PersonViewSet, 'api-persontable')

urlpatterns += router.get_urls()
