from django.db import models
from django.conf import settings

class ChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, default="New Chat")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=[('user', 'User'), ('model', 'AI')])
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class ChatDocument(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='documents')
    file_name = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True) # Extracted text
    gemini_file_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)