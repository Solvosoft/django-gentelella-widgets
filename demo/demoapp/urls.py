from django.conf.urls import url
from django.urls import path, include

from demoapp.cruds import Personclass, Countryclass, MenuItemclass
from demoapp.views import create_notification_view, color_widget_view, calendar_view
from djgentelella.permission_management import views
from .autocomplete import views as autocompleteviews
from .chartjs import chart_js_view
from .formset import add_formset, add_model_formset
from .views import knobView, YesNoInputView
from .input_masks import views as input_mask
from .date_range import views as date_ranges
from .tagging import views as tagging
from .wysiwyg import views as tinymce
from .grid_slider import views as grid
from .filechunckedupload import views as chunckedupload

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
        path('tinymce/', tinymce.InsertTinymce.as_view(), name='tinymce-add'),
        path('tinymce/list', tinymce.ListTinymce.as_view(), name='tinymce-list'),
        path('tinymce/<int:pk>', tinymce.EditTinymce.as_view(), name='tinymce-edit'),
        path('tinymce_show/<int:pk>', tinymce.DetailTinymce.as_view(), name='tinymce-show'),
        path('yesnoinput/', YesNoInputView.as_view(), name='yes-no-input-add'),
        path('gridslider/',grid.AddGrid.as_view(), name='grid-slider-add'),
        path('gridslider/list',grid.ListGrid.as_view(), name='grid-slider-list'),
        path('gridslider/<int:pk>',grid.UpdateGrid.as_view(), name='grid-slider-edit'),
        path('chunkedupload/', chunckedupload.Addchunkedupload.as_view(), name='chunkeduploaditem-add'),
        path('chunkedupload/list', chunckedupload.Listchunkedupload.as_view(), name='chunkeduploaditem-list'),
        path('chunkedupload/<int:pk>', chunckedupload.Updatechunkedupload.as_view(), name='chunkeduploaditem-edit'),
        path('calendar_view', calendar_view, name="calendar_view")
              ] + pclss.get_urls() + countryclss.get_urls() + menuclss.get_urls()