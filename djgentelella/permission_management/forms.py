from django import forms
from djgentelella.forms.forms import GTForm
from djgentelella.settings import Group, User
from django.contrib.auth.models import Permission
from djgentelella.settings import USER_MODEL_BASE, GROUP_MODEL_BASE


class FilterPermCategoryForm(GTForm, forms.Form):
    option = forms.ChoiceField(choices=((1, 'User'), (2, 'Group')), required=True)
    urlname = forms.CharField(required=True)


class PermCategoryManagementForm(GTForm, forms.Form):
    option = forms.ChoiceField(choices=((1, 'User'), (2, 'Group')), required=True)
    user = forms.ModelChoiceField(queryset=User.objects.all(), required=False)
    group = forms.ModelChoiceField(queryset=Group.objects.all(), required=False)
    permissions = forms.ModelMultipleChoiceField(queryset=Permission.objects.all(), required=False)
    urlname = forms.CharField(required=True)

    def clean_user(self):
        option = self.cleaned_data.get("option")
        user = self.cleaned_data.get("user")
        if option == 1:
            if user == "" or user is None:
                raise forms.ValidationError("Select "+USER_MODEL_BASE.split('.')[1].lower())
        return user
    
    def clean_group(self):
        option = self.cleaned_data.get("option")
        group = self.cleaned_data.get("group")
        if option ==2:
            if group == "" or group is None:
                raise forms.ValidationError("Select "+GROUP_MODEL_BASE.split('.')[1].lower())
        return group