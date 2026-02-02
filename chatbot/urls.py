from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_interface, name='chat_home'),
    path('<int:session_id>/', views.chat_interface, name='chat_interface_detail'),
    path('send/', views.send_message, name='send_message'),
    path('upload/', views.upload_document, name='upload_document'),
    path('delete-chat/<int:session_id>/', views.delete_chat_session, name='delete_chat'),
    path('delete-document/<int:doc_id>/', views.delete_document, name='delete_document'),
]