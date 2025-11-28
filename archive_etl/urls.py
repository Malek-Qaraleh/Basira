from django.urls import path
from . import views

urlpatterns = [
    path('', views.research_dashboard, name='research_dashboard'),
    path('request/<int:pk>/', views.request_detail, name='request_detail'),
    path('request/<int:pk>/csv/', views.export_research_csv, name='export_research_csv'),
]