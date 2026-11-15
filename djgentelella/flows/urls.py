from django.urls import path

from djgentelella.flows import views

# The object's pk goes last and as <path:...>: a text pk may hold a slash, and
# anything after it would otherwise be taken for the transition.
urlpatterns = [
    path('flows/inbox/', views.task_inbox, name='task_inbox'),
    path('flows/tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('flows/tasks/<int:pk>/<str:action>/', views.task_action, name='task_action'),
    path('flows/<str:flow>/inbox/', views.flow_inbox, name='flow_inbox'),
    path('flows/<str:flow>/bulk/', views.flow_bulk, name='flow_bulk'),
    path('flows/<str:flow>/diagram/', views.flow_diagram, name='flow_diagram'),
    path('flows/<str:flow>/object/<path:pk>/', views.flow_detail,
         name='flow_detail'),
    path('flows/<str:flow>/run/<str:transition>/<path:pk>/', views.flow_transition,
         name='flow_transition'),
    path('flows/<str:flow>/assign/<str:action>/<path:pk>/', views.flow_assign,
         name='flow_assign'),
    path('flows/<str:flow>/control/<str:action>/<path:pk>/', views.flow_control,
         name='flow_control'),
]
