import re
from urllib.parse import urlparse

from django import forms


class DomainSearchForm(forms.Form):
    domain = forms.CharField(
        max_length=255,
        label='Domain',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., example.com or https://example.com/'
        }),
    )

    def clean_domain(self):
        domain = self.cleaned_data['domain'].strip()

        if not domain.startswith(('http://', 'https://')):
            domain = 'https://' + domain

        try:
            parsed = urlparse(domain)
        except Exception:
            raise forms.ValidationError('Invalid domain format')

        if not parsed.netloc:
            raise forms.ValidationError('Please enter a valid domain')

        domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        if not re.match(domain_pattern, parsed.netloc):
            raise forms.ValidationError('Invalid domain format')

        return parsed.netloc

    def get_base_domain(self):
        if self.is_valid():
            return self.cleaned_data['domain']
        return None