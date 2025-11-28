from django import forms
from .models import ResearchRequest

class ResearchForm(forms.ModelForm):
    class Meta:
        model = ResearchRequest
        fields = ['topic', 'target_url', 'max_articles']
        widgets = {
            'topic': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'e.g. Economic Reform in Jordan'
            }),
            'target_url': forms.URLInput(attrs={
                'class': 'form-control', 
                'placeholder': 'https://jordantimes.com/search?q=economy'
            }),
            'max_articles': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': 1, 
                'max': 100,
                'placeholder': '10'
            }),
        }
        labels = {
            'max_articles': 'Number of Articles to Analyze'
        }