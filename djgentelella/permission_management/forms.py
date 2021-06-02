from django import forms
from djgentelella.forms.forms import GTForm
from djgentelella.settings import Group, User
from djgentelella.models import PermissionsCategoryManagement

class PermCategoryManagementForm(GTForm, forms.Form):
    type = forms.ChoiceField(choices=((1, 'User'), (2, 'Group')), required=True)
    user = forms.ModelChoiceField(queryset=User.objects.all(), required=False)
    group = forms.ModelChoiceField(queryset=Group.objects.all(), required=False)
    permissions = forms.ModelMultipleChoiceField(queryset=PermissionsCategoryManagement.objects.all())