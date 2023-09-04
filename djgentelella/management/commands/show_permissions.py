from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from djgentelella.models import PermissionRelated

class Command(BaseCommand):
    help = 'Create related permissions in the database'

    def handle(self, *args, **options):
        permissions_to_create = [


            {
                'main_permission_codename': 'change_abcde',
                'related_permissions_codenames': [
                    'add_permission',

                    # Agrega más permisos relacionados si es necesario
                ],
            },
            {
                'main_permission_codename': 'add_abcde',
                'related_permissions_codenames': [
                    'change_user',

                    # Agrega más permisos relacionados si es necesario
                ],
            },

                {
                    'main_permission_codename': 'add_peoplegroup',
                    'related_permissions_codenames': [
                        'view_user',

                        # Agrega más permisos relacionados si es necesario
                    ],
            },

            {
                'main_permission_codename': 'change_peoplegroup',
                'related_permissions_codenames': [
                    'add_user',

                    # Agrega más permisos relacionados si es necesario
                ],
            },
            # Agrega más conjuntos de permisos aquí si es necesario
        ]

        existing_permissions = Permission.objects.all()
        self.stdout.write("Existing permissions in the database:")
        for permission in existing_permissions:
            self.stdout.write(f"- {permission.codename}")

        for perm_data in permissions_to_create:
            main_permission_codename = perm_data['main_permission_codename']
            related_permissions_codenames = perm_data['related_permissions_codenames']

            try:
                main_permission = Permission.objects.get(codename=main_permission_codename)
            except Permission.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Main permission '{main_permission_codename}' not found."))
                continue

            related_permissions = Permission.objects.filter(codename__in=related_permissions_codenames)
            permission_related, _ = PermissionRelated.objects.get_or_create(main_permission=main_permission)
            permission_related.related_permissions.set(related_permissions)

            self.stdout.write(self.style.SUCCESS(f"Updated related permissions for '{main_permission}'"))

        self.stdout.write(self.style.SUCCESS('Related permissions creation completed.'))
