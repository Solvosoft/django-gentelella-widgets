"""Demo newsletter recipient interface.

Shows how a project wires ``ASYNC_NEWS_BASE_MODELS`` to compute newsletter
recipients from a filtered model queryset.
"""

from django import forms
from django.contrib.auth import get_user_model

from djgentelella.async_notification.interfaces import NewsLetterInterface

User = get_user_model()


class UserRecipientForm(forms.Form):
    is_active = forms.BooleanField(
        required=False, label='Only active users')
    is_staff = forms.BooleanField(
        required=False, label='Only staff')
    excludeemail = forms.CharField(
        required=False, label='Exclude emails (comma separated)')


class UserNewsLetterInterface(NewsLetterInterface):
    name = 'users'
    form = UserRecipientForm
    model = User
    email_field = 'email'
    field_map = {
        'filter': {
            'is_active': 'is_active',
            'is_staff': 'is_staff',
        },
        'exclude': {
            'excludeemail': 'email__in',
        },
    }
