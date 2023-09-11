from django.contrib.auth.models import Permission
from rest_framework import serializers

from djgentelella.models import PermissionRelated



class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'codename', 'name']


class PermissionRelatedSerializer(serializers.ModelSerializer):
    related_permissions = serializers.SerializerMethodField()


    def remove_permisssion(self):
        user = self.context['view'].request.user
        user_perms = list(user.user_permissions.all().values_list('id', flat=True))
        group_perms = list(user.groups.all().values_list('permissions', flat=True))
        cache_perms = list()
        if hasattr(user, '_perm_cache'):
            cache_perms = list(user._perm_cache)

        all_perms = set(user_perms + group_perms + cache_perms)
        self.list_of_perms = list(
            set(self.list_of_perms) - all_perms
        )

    def find_permission_related(self, listofid, recursion=0, max_recursion=10):
        if max_recursion == recursion:
            return

        rel_perms = set(PermissionRelated.objects.filter(
            main_permission__in=listofid
        ).values_list(
            'related_permissions', flat=True))
        rel_perms = rel_perms - set(self.list_of_perms)
        if rel_perms:
            self.list_of_perms += list(rel_perms)
            self.find_permission_related(rel_perms, recursion=recursion + 1)

    def get_related_permissions(self, obj):
        self.list_of_perms = list(
            obj.related_permissions.all().values_list('id', flat=True))

        self.find_permission_related(self.list_of_perms)
        # self.remove_permisssion()
        list_of_perms = Permission.objects.filter(pk__in=self.list_of_perms)
        return PermissionSerializer(list_of_perms, many=True).data

    class Meta:
        model = PermissionRelated
        fields = '__all__'


