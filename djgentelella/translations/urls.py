from django.urls import path

from djgentelella.translations import views

urlpatterns = [
    path('gt-translations/', views.translations_index, name='gt_translations'),
    path('gt-translations/page/<int:pk>/', views.translate_page,
         name='gt_translations_page'),
    path('gt-translations/menu/', views.translate_menu, name='gt_translations_menu'),
    path('gt-translations/lov/<str:name>/', views.translate_lov,
         name='gt_translations_lov'),
    path('gt-translations/missing/<str:language>/', views.translations_missing,
         name='gt_translations_missing'),
    path('gt-translations/export/', views.translations_export,
         name='gt_translations_export'),
    path('gt-translations/import/', views.translations_import,
         name='gt_translations_import'),
]
