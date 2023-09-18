from django.contrib.auth import get_user_model
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework.test import APIClient
from django.test import TestCase
from rest_framework import status

from demoapp.tests import unittest
from djgentelella.models import PermissionRelated


class ErrorHandlingAPITestCase(TestCase):
    def setUp(self):
        # set the client of the API
        self.client = APIClient()

    def test_dynamic_url(self):
        # Define the "id" that you want to prove
        resource_id = 123

        # Build the dynamic URL in function with the "id"
        url = f'/permsrelated/{resource_id}/'
        response = self.client.get(url)

        # The answer should be the code(404)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)









#Update



def update_related_permission(app_label, main_permission_codename, related_permission_codename, new_name, new_codename):
    global permissions_to_create
    for permission in permissions_to_create:
        if (
            permission['app_label'] == app_label
            and permission['main_permission_codename'] == main_permission_codename
            and 'related_permissions' in permission
        ):
            related_permissions = permission['related_permissions']
            for rel_perm in related_permissions:
                if rel_perm['codename'] == related_permission_codename:
                    rel_perm['name'] = new_name
                    rel_perm['codename'] = new_codename
                    return True

    return False

class TestUpdateRelatedPermission(unittest.TestCase):
    def setUp(self):
        global permissions_to_create

        permissions_to_create = [
            {
                'app_label': 'demoapp',
                'main_permission_natural_name': 'Can change abcde',
                'main_permission_codename': 'change_abcde',
                'related_permissions': [
                    {
                        'app_label': 'auth',
                        'name': 'Can add user',
                        'codename': 'add_user',
                    },
                    {
                        'app_label': 'auth',
                        'name': 'Can delete user',
                        'codename': 'delete_user',
                    },
                ],
            },
            {
                'app_label': 'demoapp',
                'main_permission_natural_name': 'Can add abcde',
                'main_permission_codename': 'add_abcde',
                'related_permissions': [
                    {
                        'app_label': 'sessions',
                        'name': 'Can add session',
                        'codename': 'add_session',
                    },
                ],
            },
        ]

    def test_update_related_permission(self):
        # Update an exisiting perm
        app_label = 'demoapp'
        main_permission_codename = 'change_abcde'
        related_permission_codename = 'add_user'
        new_name = 'Modified User Permission'
        new_codename = 'modified_add_user'

        result = update_related_permission(
            app_label, main_permission_codename, related_permission_codename, new_name, new_codename
        )

        self.assertTrue(result)  # Verify the update was correctly
        for permission in permissions_to_create:
            if (
                permission['app_label'] == app_label
                and permission['main_permission_codename'] == main_permission_codename
            ):
                for rel_perm in permission.get('related_permissions', []):
                    if rel_perm['codename'] == related_permission_codename:
                        self.assertEqual(rel_perm['name'], new_name)
                        self.assertEqual(rel_perm['codename'], new_codename)

    def test_update_related_permission_not_found(self):
        # prove if related_permission no exists in permissions_to_create
        app_label = 'demoapp'
        main_permission_codename = 'change_abcde'
        related_permission_codename = 'nonexistent_permission'
        new_name = 'Modified User Permission'
        new_codename = 'modified_nonexistent_permission'

        result = update_related_permission(
            app_label, main_permission_codename, related_permission_codename, new_name, new_codename
        )

        self.assertFalse(result)  # Verify if no update la related_permission
        for permission in permissions_to_create:
            if (
                permission['app_label'] == app_label
                and permission['main_permission_codename'] == main_permission_codename
            ):
                for rel_perm in permission.get('related_permissions', []):
                    if rel_perm['codename'] == related_permission_codename:
                        # Verificar that related_permission was not modified
                        self.assertEqual(rel_perm['name'], 'Can add user')
                        self.assertEqual(rel_perm['codename'], 'add_user')

if __name__ == '__main__':
    unittest.main()




#Delete




def remove_related_permission(app_label, main_permission_codename, related_permission_codename):
    global permissions_to_create
    for permission in permissions_to_create:
        if (
            permission['app_label'] == app_label
            and permission['main_permission_codename'] == main_permission_codename
        ):
            related_permissions = permission.get('related_permissions', [])
            updated_related_permissions = [
                rel_perm
                for rel_perm in related_permissions
                if rel_perm['codename'] != related_permission_codename
            ]
            permission['related_permissions'] = updated_related_permissions
            return True

    # if not found nothing, return false
    return False

class TestRemoveRelatedPermission(unittest.TestCase):
    def setUp(self):
        global permissions_to_create

        permissions_to_create = [
            {
                'app_label': 'demoapp',
                'main_permission_natural_name': 'Can change abcde',
                'main_permission_codename': 'change_abcde',
                'related_permissions': [
                    {
                        'app_label': 'auth',
                        'name': 'Can add user',
                        'codename': 'add_user',
                    },
                    {
                        'app_label': 'auth',
                        'name': 'Can delete user',
                        'codename': 'delete_user',
                    },
                ],
            },
            {
                'app_label': 'demoapp',
                'main_permission_natural_name': 'Can add abcde',
                'main_permission_codename': 'add_abcde',
                'related_permissions': [
                    {
                        'app_label': 'sessions',
                        'name': 'Can add session',
                        'codename': 'add_session',
                    },
                ],
            },
        ]

    def test_remove_related_permission_existing(self):
        # delete an existing related perms
        app_label = 'demoapp'
        main_permission_codename = 'change_abcde'
        related_permission_codename = 'delete_user'

        result = remove_related_permission(app_label, main_permission_codename, related_permission_codename)

        self.assertTrue(result)  # Verificar that related_permission delete
        for permission in permissions_to_create:
            if (
                permission['app_label'] == app_label
                and permission['main_permission_codename'] == main_permission_codename
            ):
                self.assertNotIn(
                    {'app_label': 'auth', 'name': 'Can delete user', 'codename': 'delete_user'},
                    permission.get('related_permissions', []),
                )

    def test_remove_related_permission_not_found(self):
        # Verifiy if main permission or related perm no exist.
        app_label = 'nonexistent_app'
        main_permission_codename = 'change_abcde'
        related_permission_codename = 'delete_user'

        result = remove_related_permission(app_label, main_permission_codename, related_permission_codename)

        self.assertFalse(result)  # Verify that not delete correctly.
        for permission in permissions_to_create:
            if (
                permission['app_label'] == app_label
                and permission['main_permission_codename'] == main_permission_codename
            ):
                # Verify that modifiy the list of perms
                self.assertEqual(
                    permission.get('related_permissions', []),
                    [
                        {'app_label': 'auth', 'name': 'Can add user', 'codename': 'add_user'},
                        {'app_label': 'auth', 'name': 'Can delete user', 'codename': 'delete_user'},
                    ],
                )

if __name__ == '__main__':
    unittest.main()





#Add



def add_related_permission(main_permission_codename, related_permissions):

    global permissions_to_create
    for permission in permissions_to_create:
        if (
            permission['main_permission_codename'] == main_permission_codename
            and 'related_permissions' in permission
        ):
            permission['related_permissions'].append(related_permissions)
            return True
    return False

class TestAddRelatedPermission(unittest.TestCase):
    def setUp(self):
        global permissions_to_create

        permissions_to_create = [
            {
                'app_label': 'demoapp',
                'main_permission_natural_name': 'Can change abcde',
                'main_permission_codename': 'change_abcde',
                'related_permissions': [
                    {
                        'app_label': 'auth',
                        'name': 'Can add user',
                        'codename': 'add_user',
                    },
                ],
            },
            {
                'app_label': 'demoapp',
                'main_permission_natural_name': 'Can add abcde',
                'main_permission_codename': 'add_abcde',
                'related_permissions': [
                    {
                        'app_label': 'sessions',
                        'name': 'Can add session',
                        'codename': 'add_session',
                    },
                ],
            },
        ]

    def test_add_related_permission(self):
        # Add related permission to main permission.
        main_permission_codename = 'change_abcde'
        related_permission = {
            'app_label': 'auth',
            'name': 'Can delete user',
            'codename': 'delete_user',
        }

        result = add_related_permission(main_permission_codename, related_permission)

        self.assertTrue(result)  # verifiy that the relation was add correctly.
        for permission in permissions_to_create:
            if permission['main_permission_codename'] == main_permission_codename:
                self.assertIn(related_permission, permission['related_permissions'])

    def test_add_related_permission_not_found(self):
        # prove if the main permission exist in the relation cretaed.
        main_permission_codename = 'nonexistent_permission'
        related_permission = {
            'app_label': 'auth',
            'name': 'Can delete user',
            'codename': 'delete_user',
        }

        result = add_related_permission(main_permission_codename, related_permission)

        self.assertFalse(result)  # Verify was not add the realtion.
        for permission in permissions_to_create:
            self.assertNotIn(related_permission, permission.get('related_permissions', []))

if __name__ == '__main__':
    unittest.main()







#Verify that the admin has acces to some specific view.


class PermissionRelatedAPITestCase(TestCase):
    def setUp(self):

        self.admin_user = get_user_model().objects.create_superuser(username='admin', password='adminpassword')

        # Create a client and authentic an user admin.
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

    def test_api_with_admin_user(self):

        permission_related = PermissionRelated.objects.create(main_permission_id=1)

        # get the API URL
        url = reverse('api_related_permissions_detail', kwargs={'permission_id': permission_related.main_permission.id})

        # Request get to the API
        response = self.client.get(url)

        # Verify that the answer is a code 200 (OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)



#Verifiy if some user has or not permissions.

class AdminPermissionsTestCase(TestCase):
    def setUp(self):

        self.admin_user = get_user_model().objects.create_superuser(username='admin', password='1234')


        self.permissions_to_create = [
            {
                'app_label': 'demoapp',
                'main_permission_codename': 'change_abcde',
                'related_permissions': [
                    {
                        'app_label': 'auth',
                        'codename': 'add_user',
                    },
                ],
            },
            {
                'app_label': 'demoapp',
                'main_permission_codename': 'add_abcde',
                'related_permissions': [
                    {
                        'app_label': 'sessions',
                        'codename': 'add_session',
                    },
                ],
            },
        ]

    def test_admin_has_specific_permissions(self):
        # Verify that the user has some of the perms related created.
        for permission_info in self.permissions_to_create:
            main_permission_codename = permission_info['main_permission_codename']
            app_label = permission_info['app_label']

            # Verify if the user some main permission.
            main_permission = f'{app_label}.{main_permission_codename}'
            if self.admin_user.has_perm(main_permission):
                self.assertTrue(True)  # User has main permission
                break  # Ouf of the loop if found a main permission.

            # Verify if the user has one of the main permissions
            related_permissions = permission_info['related_permissions']
            for related_permission_info in related_permissions:
                codename = related_permission_info['codename']
                related_permission = f'{app_label}.{codename}'
                if self.admin_user.has_perm(related_permission):
                    self.assertTrue(True)  # user has unless one main permission
                    break  # Ouf of the loop if found a main permission.
            else:
                continue  # Continue verifing other perms
            break  # # Ouf of the loop if found a related permission.
        else:
            self.assertFalse(True)  # NOt found any type of permissions








#Verify if the API has permissions.


class PermissionRelatedAPITestCase(TestCase):
    def setUp(self):

        self.admin_user = get_user_model().objects.create_superuser(username='admin', password='adminpassword')


        self.user = get_user_model().objects.create_user(username='testuser', password='testpassword')


        self.client = APIClient()

    def test_admin_has_access(self):
        # Autenthic the user
        self.client.force_authenticate(user=self.admin_user)


        permission_related = PermissionRelated.objects.create(main_permission_id=1)

        # GET the API URL
        url = reverse('api_related_permissions_detail', kwargs={'permission_id': permission_related.main_permission.id})

        # request get to the API
        response = self.client.get(url)

        # Verify that the answer is 200(ok)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_has_no_access(self):

        self.client.force_authenticate(user=self.user)


        permission_related = PermissionRelated.objects.create(main_permission_id=1)


        url = reverse('api_related_permissions_detail', kwargs={'permission_id': permission_related.main_permission.id})


        response = self.client.get(url)


        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
