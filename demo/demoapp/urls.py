from django.urls import path, include
from markitup.views import apply_filter
from rest_framework.routers import DefaultRouter

from demoapp.cruds import Personclass, Countryclass, MenuItemclass
from demoapp.views import create_notification_view, bt_modal_display
from .autocomplete import views as autocompleteviews
from .calendar.views import calendar_view
from .chartjs import chart_js_view
from .datatables.api import PersonViewSet
from .datatables.views import datatableViewExample
from .cardlist.views import cardListViewExample
from .cardlist.api import PersonViewSet as PersonCard
from .date_range import views as date_ranges
from .filechunkedupload import views as chunkedupload
from .formset import add_formset, add_model_formset
from .grid_slider import views as grid
from .input_masks import views as input_mask
from .media_upload.views import mediaupload_view
from .object_management.views import object_management
from .object_management.viewset import ObjectManagerDemoModelManagement
from .storyLine.views import storyline_view
from .storymap.views import gigapixel_view, mapbased_view
from .tagging import views as tagging
from .timeline.views import timeline_view
from .views import knobView, YesNoInputView
from .wysiwyg import views as tinymce

pclss = Personclass()
countryclss = Countryclass()
menuclss = MenuItemclass()

router = DefaultRouter()
router.register('persontableview', PersonViewSet, 'api-persontable')
router.register('personcardview', PersonCard, 'api-personcard')
router.register('objectmanagement', ObjectManagerDemoModelManagement,
                'api-objectmanagement')

urlpatterns = [

                  path('object_management', object_management,
                       name='object_management_index'),
                  path('bt_modal_display', bt_modal_display, name='bt_modal_display'),
                  path('formset', add_formset, name='add_formset'),
                  path('modelformset', add_model_formset, name='add_model_formset'),
                  path('create/notification', create_notification_view,
                       name='create_notification'),
                  path('preview/', apply_filter, name='markitup_preview'),
                  path('knobwidget/testform', knobView, name="knobwidgets"),
                  path('pgroup/', autocompleteviews.PeopleGroupList.as_view(),
                       name='pgroup-list'),
                  path('pgroup/create/', autocompleteviews.PeopleGroupAdd.as_view(),
                       name='pgroup-add'),
                  path('pgroup/<int:pk>/',
                       autocompleteviews.PeopleGroupChange.as_view(),
                       name='pgroup-edit'),
                  path('abcde/', autocompleteviews.ABCDEList.as_view(),
                       name='abcde-list'),
                  path('abcde/create/', autocompleteviews.ABCDECreate.as_view(),
                       name='abcde-add'),
                  path('abcde/<int:pk>/', autocompleteviews.ABCDEChange.as_view(),
                       name='abcde-edit'),
                  path('inputmask/', input_mask.InsertMask.as_view(),
                       name='input-mask-add'),
                  path('inputmask/<int:pk>', input_mask.EditMask.as_view(),
                       name='input-mask-edit'),
                  path('inputmask/list', input_mask.listMask.as_view(),
                       name='input-mask-list'),
                  path('daterange/', date_ranges.CreateDate.as_view(),
                       name='date-range-add'),
                  path('daterange/<int:pk>', date_ranges.UpdateDate.as_view(),
                       name='date-range-edit'),
                  path('daterange/list', date_ranges.ListDate.as_view(),
                       name='date-range-list'),
                  path('chartjs', chart_js_view, name='chartjs_view'),  # antony
                  path('tagging/', tagging.InsertTagging.as_view(),
                       name='input_tagging-add'),
                  path('tagging/<int:pk>', tagging.EditTagging.as_view(),
                       name='input_tagging-edit'),
                  path('tagging/list', tagging.ListTagging.as_view(),
                       name='input_tagging-list'),
                  path('tinymce/', tinymce.InsertTinymce.as_view(), name='tinymce-add'),
                  path('tinymce/list', tinymce.ListTinymce.as_view(),
                       name='tinymce-list'),
                  path('tinymce/<int:pk>', tinymce.EditTinymce.as_view(),
                       name='tinymce-edit'),
                  path('tinymce_show/<int:pk>', tinymce.DetailTinymce.as_view(),
                       name='tinymce-show'),
                  path('yesnoinput/', YesNoInputView.as_view(),
                       name='yes-no-input-add'),
                  path('gridslider/', grid.AddGrid.as_view(), name='grid-slider-add'),
                  path('gridslider/list', grid.ListGrid.as_view(),
                       name='grid-slider-list'),
                  path('gridslider/<int:pk>', grid.UpdateGrid.as_view(),
                       name='grid-slider-edit'),
                  path('chunkedupload/', chunkedupload.Addchunkedupload.as_view(),
                       name='chunkeduploaditem-add'),
                  path('chunkedupload/list', chunkedupload.Listchunkedupload.as_view(),
                       name='chunkeduploaditem-list'),
                  path('chunkedupload/<int:pk>',
                       chunkedupload.Updatechunkedupload.as_view(),
                       name='chunkeduploaditem-edit'),
                  path('calendar_view', calendar_view, name="calendar_view"),
                  path('gigapixel_view', gigapixel_view, name="gigapixel_view"),
                  path('mapbased_view', mapbased_view, name="mapbased_view"),
                  path('storyline_view', storyline_view, name="storyline_view"),
                  path('timeline_view', timeline_view, name="timeline_view"),
                  path('datatable_view', datatableViewExample, name="datatable_view"),
                  # CardTable
                  path('cardlist_view', cardListViewExample, name="cardlist_view"),
                  path('mediarecord_upload', mediaupload_view, name="mediaupload_view"),
                  path('tableapi/', include(router.urls)),
                  path('cardapi/', include(router.urls)),
              ] + pclss.get_urls() + countryclss.get_urls() + menuclss.get_urls()
