from django.db import models
from django.conf import settings

class ChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, default="New Chat")
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional: Link to a specific dataset context
    related_batch_id = models.IntegerField(null=True, blank=True, help_text="ID of a ScrapeBatch or ResearchRequest")
    context_type = models.CharField(max_length=20, choices=[('ecommerce', 'E-Commerce'), ('research', 'Research')], default='research')

    def __str__(self):
        return self.title

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=[('user', 'User'), ('model', 'AI')])
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)