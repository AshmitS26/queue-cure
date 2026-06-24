from django.urls import path
from clinic import views

urlpatterns = [
    path('checkin/', views.api_checkin),
    path('queue/<str:clinic_id>/<str:doctor_id>/', views.api_queue),
    path('token/<str:token_id>/', views.api_token_status),
    path('next/<str:clinic_id>/<str:doctor_id>/', views.api_call_next),
    path('done/<str:clinic_id>/<str:doctor_id>/', views.api_mark_done),
    path('status/<str:token_id>/', views.api_update_status),
    path('stats/<str:clinic_id>/<str:doctor_id>/', views.api_stats),
    path('doctors/<str:clinic_id>/', views.api_doctors),
    path('liveboard/<str:clinic_id>/', views.api_live_board),
    path('reset/<str:clinic_id>/', views.api_reset),
    path('demo/populate/', views.api_demo_populate),
]
