from io import StringIO
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User, Permission
from django.urls import reverse
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework import status
from djgentelella.permission_management.serializers import PermissionRelatedSerializer
from djgentelella.management.commands.show_permissions import Command
import unittest
from django.test import TestCase
from djgentelella.models import PermissionRelated
from unittest.mock import patch



class ErrorHandlingAPITestCase(TestCase):

    # this unit test verifies the error handling behavior
    # of an API view in Django by making a request
    # to a dynamic URL with a specific resource_id
    # value and ensuring that the view responds with a 404 status code
    # if the resource is not found.
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

    # Update


def update_related_permission(app_label, main_permission_codename, related_permission_codename, new_name,  new_codename):

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

    # this unit test verifies that the update_related_permission
    # function can correctly update
    # existing related permissions and properly handles the situation
    # where the related permission is not found in the list of existing permissions.
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
        # Update an existing perm
        app_label = 'demoapp'
        main_permission_codename = 'change_abcde'
        related_permission_codename = 'add_user'
        new_name = 'Modified User Permission'
        new_codename = 'modified_add_user'

        result = update_related_permission(
            app_label, main_permission_codename, related_permission_codename,
            new_name, new_codename
        )

        self.assertTrue(result)
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
            app_label, main_permission_codename, related_permission_codename, new_name,
            new_codename
        )

        self.assertFalse(result)  # Verify if no update la related_permission
        for permission in permissions_to_create:
            if (
                permission['app_label'] == app_label
                and permission['main_permission_codename'] == main_permission_codename
            ):
                for rel_perm in permission.get('related_permissions', []):
                    if rel_perm['codename'] == related_permission_codename:
                        # Verify that related_permission was not modified
                        self.assertEqual(rel_perm['name'], 'Can add user')
                        self.assertEqual(rel_perm['codename'], 'add_user')

    if __name__ == '__main__':
        unittest.main()

    # Delete


def remove_related_permission(app_label,
                              main_permission_codename,
                              related_permission_codename):

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

    # if not found return false
        return False


class TestRemoveRelatedPermission(unittest.TestCase):
    # this unit test verifies that the remove_related_permission function can correctly
    # remove existing related permissions and properly handles the situation
    # where the main permission or related permission does not exist in the
    # list of existing permissions.

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

        result = remove_related_permission(app_label, main_permission_codename,
                                           related_permission_codename)

        self.assertTrue(result)  # Verify that related_permission delete
        for permission in permissions_to_create:
            if (
                permission['app_label'] == app_label
                and permission['main_permission_codename'] == main_permission_codename
            ):
                self.assertNotIn(
                    {'app_label': 'auth', 'name': 'Can delete user',
                     'codename': 'delete_user'},
                    permission.get('related_permissions', []),
                )

    def test_remove_related_permission_not_found(self):
        # Verify if main permission or related perm no exist.
        app_label = 'nonexistent_app'
        main_permission_codename = 'change_abcde'
        related_permission_codename = 'delete_user'

        result = remove_related_permission(app_label, main_permission_codename,
                                           related_permission_codename)

        self.assertFalse(result)  # Verify that not delete correctly.
        for permission in permissions_to_create:
            if (
                permission['app_label'] == app_label
                and permission['main_permission_codename'] == main_permission_codename
            ):
                # Verify that modify the list of perms
                self.assertEqual(
                    permission.get('related_permissions', []),
                    [
                        {'app_label': 'auth', 'name': 'Can add user',
                         'codename': 'add_user'},
                        {'app_label': 'auth', 'name': 'Can delete user',
                         'codename': 'delete_user'},
                    ],
                )

    if __name__ == '__main__':
        unittest.main()

    # Add


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
    # this unit test verifies that the add_related_permission function can
    # correctly add related permissions to existing main
    # permissions and properly handles the situation
    # where the main permission does not exist in the list of existing permissions.
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

        self.assertTrue(result)  # verifiy that the relation was  correctly.
        for permission in permissions_to_create:
            if permission['main_permission_codename'] == main_permission_codename:
                self.assertIn(related_permission, permission['related_permissions'])

    def test_add_related_permission_not_found(self):
        # prove if the main permission exist in the relation created.
        main_permission_codename = 'nonexistent_permission'
        related_permission = {
            'app_label': 'auth',
            'name': 'Can delete user',
            'codename': 'delete_user',
        }

        result = add_related_permission(main_permission_codename, related_permission)

        self.assertFalse(result)  # Verify was not add the relation.
        for permission in permissions_to_create:
            self.assertNotIn(related_permission, permission.get('related_permissions', []))

    if __name__ == '__main__':
        unittest.main()

# Verify that the admin has access to some specific view.


class PermissionTestApiCase(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(username='admin', password='adminpassword')
        # Create a client and authentic an user admin.
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

    def test_api_with_admin_user(self):
        permission_related = PermissionRelated.objects.create(main_permission_id=1)
        # get the API URL
        url = reverse('api_related_permissions_detail',
                      kwargs={'permission_id': permission_related.main_permission.id})
        # Request get to the API
        response = self.client.get(url)
        # Verify that the answer is a code 200 (OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AdminPermissionsTestCase(TestCase):
    # this test checks if an administrator user has at least one of the
    # main permissions or at least one of the related permissions for each
    # application specified in the permissions_to_create list.
    # If the administrator user has at least one of these
    # permissions, the test is considered successful.
    # If it does not have any of the specified permissions, the test fails.
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
            main_permission = f'{app_label}.{main_permission_codename}'
            if self.admin_user.has_perm(main_permission):
                self.assertTrue(True)
                break

            related_permissions = permission_info['related_permissions']
            for related_permission_info in related_permissions:
                codename = related_permission_info['codename']
                related_permission = f'{app_label}.{codename}'
                if self.admin_user.has_perm(related_permission):
                    self.assertTrue(True)
                    break
            else:
                continue
            break
        else:
            self.assertFalse(True)


class PermissionRelatedAPITestCase(TestCase):
    # Verify if the API has permissions.
    # this unit test verifies that the administrator
    # user has proper access to a specific API view (code 200 OK),
    # while the regular user does not have access (code 403 FORBIDDEN).
    # This is achieved by authenticating users and
    # making GET requests to the API view with different user roles.
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(username='admin', password='adminpassword')
        self.user = get_user_model().objects.create_user(username='testuser',
                                                         password='testpassword')
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


class PermissionRelatedSerializerTestCase(TestCase):
    # Input data validation
    # these unit tests verify the serializer's ability to
    # validate valid data and identify invalid data,
    # as well as the handling of exceptions and API errors when
    # trying to access non-existent resources.
    def test_valid_data(self):
        # Create valid input data
        data = {
            'main_permission_natural_name': 'Can change abcde',
            'main_permission_codename': 'change_abcde',
            'related_permissions': [
                {
                    'app_label': 'auth',
                    'name': 'Can add user',
                    'codename': 'add_user',
                },
            ],
        }
        # Validate the data using the serializer
        serializer = PermissionRelatedSerializer(data=data)
        # Verify that the data is valid
        self.assertTrue(serializer.is_valid())

    def test_invalid_data(self):
        # Create invalid input data (e.g., main permission with no related permissions)
        data = {
            'main_permission_natural_name': 'Can change abcde',
            'main_permission_codename': 'change_abcde',
            'related_permissions': [],  # No related permissions
        }
        # Validate the data using the serializer
        serializer = PermissionRelatedSerializer(data=data)
        # Verify that the data is invalid
        self.assertFalse(serializer.is_valid())


# Exception and error handling test for your API
# Passed test
class ExceptionHandlingTest(TestCase):
    def setUp(self):
        # Create a test API client
        self.client = APIClient()

    def test_nonexistent_resource(self):
        # Try to access a non-existent resource (e.g., using a non-existent ID)
        response = self.client.get(
            reverse('api_related_permissions_detail', args=[10000000000]))

        # Verify that the response is a 404 (Not Found) status code
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# Security test for malicious SQL injection
# Received an OK, passed test
# this unit test seeks to test the security of the API when
# attempting to perform SQL injection by including malicious data in a request.
# The test verifies that the API does not generate an internal
# server error (HTTP 500) as a result of SQL injection.
# If the API is properly protected, the test should be
# successful and the status code of the response
# should not be 500.
class SecurityTest(TestCase):
    # Test for creating related permissions in the command
    # this unit test seeks to test the security of the API when attempting to perform
    # SQL injection by including malicious data in a request.
    # The test verifies that the API does not generate an
    # internal server error (HTTP 500) as a result of SQL injection.
    # If the API is properly protected, the test should be successful
    # and the status code of the response should not be 500.
    def setUp(self):
        # Create a test API client
        self.client = APIClient()

    def test_sql_injection(self):
        malicious_data = {
            'main_permission': "' OR 1=1 --",
            'related_permissions': [2, 3]
        }
        response = self.client.post(
            reverse('api_related_permissions_detail', kwargs={'permission_id': 1}),
            malicious_data, format='json')

        self.assertNotEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestCreateRelatedPermissionsCommand(TestCase):
    def setUp(self):
        # Create an instance of the command
        self.command = Command()

    def test_create_related_permissions(self):

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

        for perm_data in permissions_to_create:
            self.command.create_related_permissions(perm_data)

            # Verify that permissions and relationships were created correctly
            main_permission = Permission.objects.get(
                content_type__app_label=perm_data['app_label'],
                name=perm_data['main_permission_natural_name'],
                codename=perm_data['main_permission_codename']
            )
            self.assertIsNotNone(main_permission)

            related_permissions = Permission.objects.filter(
                content_type__app_label=perm_data['app_label'],
                codename__in=[p['codename'] for p in perm_data['related_permissions']]
            )

            permission_related = PermissionRelated.objects.get(main_permission=main_permission)
            self.assertEqual(permission_related.related_permissions.count(),
                             len(perm_data['related_permissions']))


class TestCreateRelatedPermissionsListCommand(TestCase):
    # Test to get an empty list of permissions
    # this unit test verifies the behavior
    # of a function that imports and retrieves
    # the list of permissions from a specific module of a Django application.
    # The test focuses on how the function
    # handles the lack of a permission list in the module,
    # making sure that it returns an empty list or None in that case.
    def test_import_module_app_gt_missing_permissions_list(self):
        # Test that the function returns an empty list when the
        # "gt permissions" module does not contain a permissions_to_create list.
        app_with_missing_permissions = 'demoapp'

        with patch('demoapp.gtpermissions.permissions_to_create', None):
            permissions = self.import_module_app_gt(app_with_missing_permissions,
                                                    'gtpermissions')
        # Check if permissions are a list or None
        self.assertTrue(isinstance(permissions, list) or permissions is None)
        self.assertListEqual(permissions or [], [])

    def import_module_app_gt(self, app, name):
        try:
            variable = __import__(app + '.' + name)
            permissions = getattr(variable.gtpermissions, 'permissions_to_create', [])
            return permissions
        except ModuleNotFoundError as e:
            pass
        except AttributeError as e:
            print(f"Attribute error: {str(e)}")
        return []


if __name__ == '__main__':
    unittest.main()


class TestCreateRelatedPermissionsCommandGT(TestCase):
    # Test to get permissions
    # This test focuses on verifying that the function can correctly
    # retrieve a list of valid permissions
    # from the gt permissions module. If the function does so successfully,
    # the test will be successful and the retrieved list of permissions
    # should be identical to the list of valid permissions provided.
    def test_import_module_app_gt_with_permissions(self):
        app_with_permissions = 'demoapp'
        permissions_list = [
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
        ]  # List of valid permissions

        with patch('demoapp.gtpermissions.permissions_to_create', permissions_list):
            permissions = self.import_module_app_gt(app_with_permissions,
                                                    'gtpermissions')

        # Check if permissions are a list
        self.assertTrue(isinstance(permissions, list))
        self.assertListEqual(permissions, permissions_list)

    def import_module_app_gt(self, app, name):
        try:
            variable = __import__(app + '.' + name)
            return variable.gtpermissions.permissions_to_create
        except ModuleNotFoundError as e:
            pass
        except AttributeError as e:
            print(f"Attribute error: {str(e)}")
        return []

    # Add the rest of the tests and test methods here...


if __name__ == '__main__':
    unittest.main()


# Test for non-existent permissions
# this unit test verifies the handling of a custom Django command when it is provided
# with a dataset containing a non-existent primary permission.
# The test ensures that the command generates an appropriate warning message and
# does not create related permissions in the database in this scenario.
class TestCreateRelatedPermissionsCommandNoneExistent(TestCase):

    def setUp(self):
        # Create an instance of the command
        self.command = Command()

    def test_handle_nonexistent_main_permission(self):
        # Define a dataset with a main permission that does not exist
        permissions_to_create = [
            {
                'app_label': 'demoapp',
                'main_permission_natural_name': 'Nonexistent permission',
                'main_permission_codename': 'nonexistent_permission',
                'related_permissions': [
                    {
                        'app_label': 'auth',
                        'name': 'Can add user',
                        'codename': 'add_user',
                    },
                ],
            },
        ]

        # Capture standard output to check for the warning message
        out = StringIO()
        self.command.stdout = out

        # Call the create_related_permissions method with the dataset
        for perm_data in permissions_to_create:
            self.command.create_related_permissions(perm_data)

            # Check if the warning message was generated
            expected_warning_message = f"Main permission '{perm_data['app_label']}.{perm_data['main_permission_natural_name']}' not found."
            self.assertIn(expected_warning_message, out.getvalue())

            # Verify that related permissions were not created
            main_permission = Permission.objects.filter(
                content_type__app_label=perm_data['app_label'],
                name=perm_data['main_permission_natural_name'],
                codename=perm_data['main_permission_codename']
            ).first()
            self.assertIsNone(main_permission)

            permission_related = PermissionRelated.objects.filter(main_permission=main_permission)
            self.assertFalse(permission_related.exists())

    # You can add more test methods for other scenarios as needed


# Test for missing related permissions
# this unit test verifies the handling
# of a custom Django command when it is provided
# with a dataset containing a main
# permission that references non-existent related permissions.
# The test ensures that the command generates an appropriate warning message and
# only creates the main permission in the database in this scenario.
class TestRelatedPermissionsCommand(TestCase):

    def setUp(self):
        # Create an instance of the command
        self.command = Command()

    def test_handle_missing_related_permissions(self):
        # Define a dataset with a main permission that
        # references nonexistent related permissions

        permissions_to_create = [
            {
                'app_label': 'demoapp',
                'main_permission_natural_name': 'Can change abcde',
                'main_permission_codename': 'change_abcde',
                'related_permissions': [
                    {
                        'app_label': 'auth',
                        'name': 'Nonexistent related permission',
                        'codename': 'nonexistent_related_permission',
                    },
                ],
            },
        ]

        # Capture standard output to check for the warning message
        out = StringIO()
        self.command.stdout = out

        # Call the create_related_permissions method with the dataset
        for perm_data in permissions_to_create:
            self.command.create_related_permissions(perm_data)

            # Check if the warning message was generated
            expected_warning_message = f"Main permission '{perm_data['app_label']}.{perm_data['main_permission_natural_name']}' not found."
            self.assertIn(expected_warning_message, out.getvalue())

            # Verify that the main permission was created
            main_permission = Permission.objects.filter(
                content_type__app_label=perm_data['app_label'],
                name=perm_data['main_permission_natural_name'],
                codename=perm_data['main_permission_codename']
            ).first()
            self.assertIsNotNone(main_permission)

            # Verify that related permissions were not created
            related_permissions = Permission.objects.filter(
                content_type__app_label=perm_data['app_label'],
                name=perm_data['related_permissions'][0]['name'],
                codename=perm_data['related_permissions'][0]['codename']
            )
            self.assertFalse(related_permissions.exists())

            permission_related = PermissionRelated.objects.filter(main_permission=main_permission)
            self.assertFalse(permission_related.exists())

# Get specific permission to the API
# this test ensures that the API is able to correctly retrieve the details
# of a specific PermissionRelated object and that the API response is consistent with
# the data stored in the database for that object.


class PermissionRelatedAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.permission_related = PermissionRelated.objects.create(
            main_permission_id=110,
        )

    def test_retrieve_permission_related_detail_happy_path(self):
        url = reverse('api_related_permissions_detail',
                      kwargs={'permission_id': self.permission_related.main_permission_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['main_permission'],
                         self.permission_related.main_permission_id)

# non permission using URL
# this test ensures that the API correctly handles the request for details
# of a PermissionRelated object that does not exist in the database,
# returning a 404 status code to indicate that the resource is not found.
    def test_retrieve_nonexistent_permission_related_detail(self):
        nonexistent_permission_id = 9999
        url = reverse('api_related_permissions_detail',
                      kwargs={'permission_id': nonexistent_permission_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PermissionRelatedDetailViewTestCase(TestCase):

    # Test of view set of the API
    # this test ensures that the PermissionRelatedDetailView
    # is able to retrieve and display
    # the details of an existing PermissionRelated
    # object in the database in response to a GET request.

    def setUp(self):
        self.permission_related = PermissionRelated.objects.create(
            main_permission_id=103
        )
        self.user = User.objects.create(username='test user', password='password')

    def test_permission_related_detail_success_response(self):
        factory = APIRequestFactory()
        url = reverse('api_related_permissions_detail',
                      kwargs={'permission_id': self.permission_related.main_permission_id})
        request = factory.get(url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_data = PermissionRelatedSerializer(self.permission_related).data
        self.assertEqual(response.data, expected_data)
