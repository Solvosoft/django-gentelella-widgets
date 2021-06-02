from django import forms
from djgentelella.forms.forms import GTForm
from djgentelella.settings import Group, User
from djgentelella.models import PermissionsCategoryManagement
from djgentelella.settings import USER_MODEL_BASE, GROUP_MODEL_BASE


class PermCategoryManagementForm(GTForm, forms.Form):
    type = forms.ChoiceField(choices=((1, 'User'), (2, 'Group')), required=True)
    user = forms.ModelChoiceField(queryset=User.objects.all(), required=False)
    group = forms.ModelChoiceField(queryset=Group.objects.all(), required=False)
    permissions = forms.ModelMultipleChoiceField(queryset=PermissionsCategoryManagement.objects.all(), required=False)

    def clean_user(self):
        type = self.cleaned_data.get("type")
        user = self.cleaned_data.get("user")
        if type == 1:
            if user == "" or user is None:
                raise forms.ValidationError("Select "+USER_MODEL_BASE.split('.')[1].lower())
        return user
    
    def clean_group(self):
        type = self.cleaned_data.get("type")
        group = self.cleaned_data.get("group")
        if type ==2:
            if group == "" or group is None:
                raise forms.ValidationError("Select "+GROUP_MODEL_BASE.split('.')[1].lower())
        return group