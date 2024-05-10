'''
Created on 1/8/2016

@author: luisza
'''

from django.urls import path, re_path
from . import views
from django.conf import settings

urlpatterns = [
    path("create", views.CreateReservation.as_view(), name="add_user_reservation"),
    path("finish", views.finish_reservation, name="finish_reservation"),
    path("delete_product_reservation/<int:pk>/", views.deleteProduct, name="delete_product_reservation"),
    path("list", views.ReservationList.as_view(), name="reservation_list"),
]

if settings.TOKENIZE:
    urlpatterns += [
        re_path(r"token/(?P<pk>\d+)/(?P<token>[0-9a-f-]+)/(?P<status>\d)$",
            views.update_reservation_by_token,
            name="reservation_token")
    ]
