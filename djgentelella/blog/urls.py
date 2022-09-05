
from django.urls import path, re_path

from . import views

app_name = 'blog'
urlpatterns = [
    path('', views.EntriesList.as_view(), name='entrylist'),
    path('entry/create', views.EntryCreate.as_view(), name='entrycreate'),
    path('entry/<int:pk>/', views.EntryUpdate.as_view(), name='entry_update'),
    path('entry/<int:pk>/delete', views.EntryDelete.as_view(), name='entry_delete'),
    path('category/create', views.category_add, name='category_add'),
    re_path(r'^published/(?P<slug>[A-Za-z0-9-_]+)/$', views.EntryDetail.as_view(), name='entrydetail'),
]