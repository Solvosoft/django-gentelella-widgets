from django.conf.urls import url
from django.urls import path, include

from demoapp.cruds import Personclass, Countryclass, MenuItemclass
from demoapp.views import create_notification_view, color_widget_view
from .autocomplete import views as autocompleteviews
from .chartjs import chart_js_view
from .formset import add_formset, add_model_formset
from .views import knobView
from .input_masks import views as input_mask
from .date_range import views as date_ranges
from .tagging import views as tagging

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
        path('daterange/<int:pk>',date_ranges.UpdateDate.as_view(), name='date-range-edit'),
        path('daterange/list',date_ranges.ListDate.as_view(), name='date-range-list'),
        path('chartjs', chart_js_view, name='chartjs_view'),
        path('tagging/', tagging.InsertTagging.as_view(), name='input_tagging-add'),
        path('tagging/<int:pk>', tagging.EditTagging.as_view(), name='input_tagging-edit'),
        path('tagging/list', tagging.ListTagging.as_view(), name='input_tagging-list'),

] + pclss.get_urls() + countryclss.get_urls() + menuclss.get_urls()