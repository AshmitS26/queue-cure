import os
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path, include
from clinic import views

urlpatterns = [
    # Public pages
    path('', views.home, name='home'),
    path('checkin/', views.patient_checkin_page, name='checkin'),
    path('status/<str:token_id>/', views.patient_status_page, name='status'),
    path('qr/<str:clinic_id>/', views.clinic_qr, name='clinic_qr'),
    path('demo/', views.demo_page, name='demo'),

    # Auth
    path('login/<str:role>/', views.login_view, name='login'),
    path('logout/<str:role>/', views.logout_view, name='logout'),

    # Protected pages
    path('receptionist/', views.receptionist_page, name='receptionist'),
    path('doctor/', views.doctor_page, name='doctor'),

    # API
    path('api/', include('clinic.urls')),
]

# Serve static files in development
if os.environ.get('DEBUG', 'True') == 'True':
    urlpatterns += staticfiles_urlpatterns()
