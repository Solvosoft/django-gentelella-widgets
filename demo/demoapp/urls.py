from django.conf.urls import url
from django.urls import path, include

from demoapp.cruds import Personclass, Countryclass, MenuItemclass
from demoapp.views import create_notification_view, color_widget_view
from .autocomplete import views as autocompleteviews
from .formset import add_formset, add_model_formset
from .views import knobView
from .input_masks import views as input_mask
from .date_range import views as date_ranges

pclss = Personclass()
countryclss = Countryclass()
menuclss = MenuItemclass()

urlpatterns = [
        path('formset', add_formset, name='add_formset'),
        path('modelformset', add_model_formset, name='add_model_formset'),
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
        path('inputmask/',input_mask.InsertMask.as_view(), name='input-mask-add'),
        path('inputmask/<int:pk>',input_mask.EditMask.as_view(), name='input-mask-edit'),
        path('inputmask/list',input_mask.listMask.as_view(), name='input-mask-list'),
        path('daterange/',date_ranges.CreateDate.as_view(), name='date-range-add'),

] + pclss.get_urls() + countryclss.get_urls() + menuclss.get_urls()