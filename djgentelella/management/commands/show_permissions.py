from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from djgentelella.models import PermissionRelated
from djgentelella.permissions import permissions_to_create


class Command(BaseCommand):
    help = 'Create related permissions in the database'

    def handle(self, *args, **options):

        existing_permissions = Permission.objects.all()
        self.stdout.write("Existing permissions in the database:")
        for permission in existing_permissions:
            self.stdout.write(f"- {permission.content_type.app_label}: {permission.name} ({permission.codename})")

        for perm_data in permissions_to_create:
            app_label = perm_data['app_label']
            main_permission_natural_name = perm_data['main_permission_natural_name']
            main_permission_codename = perm_data['main_permission_codename']
            related_permissions_data = perm_data['related_permissions']

            main_permission = Permission.objects.filter(
                content_type__app_label=app_label,
                name=main_permission_natural_name,
                codename=main_permission_codename
            ).first()

            if not main_permission:
                self.stdout.write(self.style.WARNING(
                    f"Main permission '{app_label}.{main_permission_natural_name}' not found."))
                continue

            related_permissions = []
            for related_perm_data in related_permissions_data:
                app_label_related = related_perm_data['app_label']
                name_related = related_perm_data['name']
                codename_related = related_perm_data['codename']

                related_permission = Permission.objects.filter(
                    content_type__app_label=app_label_related,
                    name=name_related,
                    codename=codename_related
                ).first()
                if related_permission:
                    related_permissions.append(related_permission)

            permission_related, _ = PermissionRelated.objects.get_or_create(
                main_permission=main_permission)
            permission_related.related_permissions.set(related_permissions)

            self.stdout.write(self.style.SUCCESS(
                f"Updated related permissions for '{app_label}.{main_permission_natural_name}'"))
