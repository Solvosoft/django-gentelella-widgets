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
# add permissions

def add_related_permission(main_permission_codename, related_permissions):
    for permission in permissions_to_create:
        if (
            permission['main_permission_codename'] == main_permission_codename
            and 'related_permissions' in permission
        ):
            permission['related_permissions'].append(related_permissions)
            return True
    return False




#delete permissions
def remove_related_permission(app_label, main_permission_codename, related_permission_codename):
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




#update permissions
def update_related_permission(app_label, main_permission_codename, related_permission_codename, new_name, new_codename):
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


