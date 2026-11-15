from django.urls import path, re_path

from djgentelella.designs import views

urlpatterns = [
    re_path(r'^gtapis/designs/(?P<page_id>\d+)/(?P<node_id>[a-z][a-z0-9_]*)/'
            r'(?P<rest>.*)$', views.design_endpoint, name='gt-design-endpoint'),
    path('designs/<path:path>', views.design_page, name='gt-design-page'),
]
