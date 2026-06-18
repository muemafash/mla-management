from django import forms
from .models import Result, Student


class ResultForm(forms.ModelForm):
    class Meta:
        model = Result
        fields = ['student', 'exam', 'subject', 'score']
        widgets = {
            'exam': forms.TextInput(attrs={'placeholder': 'e.g. Midterm 2026'}),
            'subject': forms.TextInput(attrs={'placeholder': 'e.g. Mathematics'}),
            'score': forms.NumberInput(attrs={'step': '0.01'}),
        }
