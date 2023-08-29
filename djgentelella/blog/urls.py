from django.urls import path, re_path
from rest_framework.routers import DefaultRouter
from . import views
from demoapp.datatables.api import PersonViewSet

from djgentelella.datatables.api import BlogViewSet

from djgentelella.blog.views import object_blog
from djgentelella.blog.viewset import ObjectBLog

from demoapp.cruds import Personclass





pclss = Personclass()
router = DefaultRouter()
router.register('blogtableview', BlogViewSet, 'api-blogtable')
router.register('objectbLog', ObjectBLog,
                'api-objectbLog')

app_name = 'blog'
urlpatterns = [

    path('object_blog', object_blog,
         name='object_blog'),
    path('', views.EntriesList.as_view(), name='entrylist'),
    path('entry/create', views.EntryCreate.as_view(), name='entrycreate'),
    path('entry/<int:pk>/', views.EntryUpdate.as_view(), name='entry_update'),
    path('entry/<int:pk>/delete', views.EntryDelete.as_view(), name='entry_delete'),
    path('category/create', views.category_add, name='category_add'),
    re_path(r'^published/(?P<slug>[A-Za-z0-9-_]+)/$', views.EntryDetail.as_view(),
            name='entrydetail'),
]
