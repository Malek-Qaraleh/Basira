"""
URL configuration for webscraper project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from core import views as core_views


urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Homepage
    path('', core_views.home, name='home'),

    # Your scrape form page
    path('scrape/', core_views.scrape, name='scrape'), 
    
    # Your dashboard results page
    path('dashboard/<int:batch_id>/', core_views.dashboard, name='dashboard'),

    # Auth URLs
    path('register/', core_views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # History & Export URLs
    path('history/', core_views.history, name='history'),
    path('batch/<int:batch_id>/status/', core_views.job_status, name='job_status'),
    path('batch/<int:batch_id>/export/csv/', core_views.export_csv, name='export_csv'),
    path('batch/<int:batch_id>/export/json/', core_views.export_json, name='export_json'),
    path('research/', include('archive_etl.urls')),
    path('chatbot/',include('chatbot.urls'))
]