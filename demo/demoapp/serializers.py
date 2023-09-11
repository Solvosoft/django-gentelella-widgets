from django.contrib.auth.models import Permission

from rest_framework import serializers
from demoapp.models import PermissionRelation


# class PermissionSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Permission
#         fields = ['id', 'name', 'content_type', 'codename']

class PermissionRelationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermissionRelation
        fields = '__all__'
