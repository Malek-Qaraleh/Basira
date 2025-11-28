# In core/forms.py

from django import forms
from django.contrib.auth.models import User

# --- User registration form ---
class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    class Meta:
        model = User
        fields = ('username', 'email', 'password')

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password') != cleaned_data.get('password_confirm'):
            self.add_error('password_confirm','Passwords do not match')
        return cleaned_data

# --- This is the ScrapeForm for your dashboard ---
class ScrapeForm(forms.Form):
    query = forms.CharField(
        label="Search Query (Paste URL here)",
        max_length=1024,
        widget=forms.URLInput(attrs={'placeholder': 'https://www.dumyah.com/...'}),
        required=True
    )
    
    max_items = forms.IntegerField(
        label="Max Items (0 = all)",
        min_value=0,
        initial=100, 
        required=True
    )
    max_pages = forms.IntegerField(
        label="Max Pages (0 = all)",
        min_value=0,
        initial=0, 
        required=True
    )