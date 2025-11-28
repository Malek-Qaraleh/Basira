from django.urls import path
from . import views

urlpatterns = [
    # Redirects to latest chat or creates new one
    path('', views.chat_redirect, name='chat_home'), 
    
    # The main chat interface (now handles both history and active chat)
    path('<int:session_id>/', views.chat_room, name='chat_room'),
    
    path('create/', views.create_session, name='create_session'),
    path('<int:session_id>/send/', views.send_message, name='send_message'),
]