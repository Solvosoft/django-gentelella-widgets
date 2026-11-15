"""The "add" button of the catalog widgets, limited by ``add_perms`` (#116).

The widget does not see the request: ``UserBoundWidgetsMixin`` gives it the
user, and without one a widget with ``add_perms`` shows no button.
"""

from django import forms
from django.contrib.auth.models import AnonymousUser, Permission, User
from django.test import RequestFactory, TestCase

from djgentelella.forms.forms import (
    GTForm,
    UserBoundWidgetsMixin,
    UserScopedUploadsMixin,
)
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets.selectmultiple import FilteredSelectMultiple
from djgentelella.widgets.trees import TreeSelectMultipleWithAdd, TreeSelectWithAdd

CHOICES = [('a', 'A'), ('b', 'B')]
PERM = 'auth.add_group'
ADD = {'add_url': '/add/'}


def add_widgets(**kwargs):
    """Every widget with an add button, built with the same ``kwargs``."""
    return {
        'select': genwidgets.SelectWithAdd(attrs=dict(ADD), **kwargs),
        'multiple': genwidgets.SelectMultipleAdd(attrs=dict(ADD), **kwargs),
        'tree': TreeSelectWithAdd(attrs=dict(ADD), **kwargs),
        'treemultiple': TreeSelectMultipleWithAdd(attrs=dict(ADD), **kwargs),
    }


def form_class(**kwargs):
    fields = {}
    for name, widget in add_widgets(**kwargs).items():
        field = (forms.MultipleChoiceField if widget.allow_multiple_selected
                 else forms.ChoiceField)
        fields[name] = field(choices=CHOICES, required=False, widget=widget)
    return type('AddForm', (UserBoundWidgetsMixin, GTForm, forms.Form), fields)


class AddPermissionTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.allowed = User.objects.create_user('allowed')
        app_label, codename = PERM.split('.')
        cls.allowed.user_permissions.add(Permission.objects.get(
            content_type__app_label=app_label, codename=codename))
        cls.denied = User.objects.create_user('denied')

    def assertButton(self, form, shown):
        for name in ('select', 'multiple', 'tree', 'treemultiple'):
            html = str(form[name])
            with self.subTest(widget=name, shown=shown):
                check = self.assertIn if shown else self.assertNotIn
                check('gentelella_select_add', html)
                check('id="modal_%s_id"' % name, html)
                check('data-modalname', html)
                self.assertIn('<select name="%s"' % name, html)


class AddPermsTests(AddPermissionTestCase):

    def test_without_add_perms_the_button_is_always_there(self):
        self.assertButton(form_class()(), shown=True)
        self.assertButton(form_class()(user=self.denied), shown=True)

    def test_a_user_with_the_permission_sees_the_button(self):
        self.assertButton(form_class(add_perms=PERM)(user=self.allowed), shown=True)

    def test_a_user_without_it_gets_the_bare_select(self):
        self.assertButton(form_class(add_perms=PERM)(user=self.denied), shown=False)

    def test_anonymous_gets_the_bare_select(self):
        self.assertButton(form_class(add_perms=PERM)(user=AnonymousUser()),
                          shown=False)

    def test_no_user_bound_fails_closed(self):
        self.assertButton(form_class(add_perms=PERM)(), shown=False)

    def test_the_user_comes_from_the_request_too(self):
        request = RequestFactory().get('/')
        request.user = self.allowed
        self.assertButton(form_class(add_perms=PERM)(request=request), shown=True)

    def test_every_permission_is_required(self):
        form = form_class(add_perms=[PERM, 'auth.delete_group'])(user=self.allowed)
        self.assertButton(form, shown=False)

    def test_add_perms_in_attrs_and_out_of_the_html(self):
        widget = genwidgets.SelectWithAdd(attrs={**ADD, 'add_perms': PERM})
        self.assertEqual(widget.add_perms, (PERM,))
        widget.bind_user(self.denied)
        html = widget.render('select', None)
        self.assertNotIn('add_perms', html)
        self.assertNotIn('gentelella_select_add', html)

    def test_can_add_overrides_the_permissions(self):
        form = form_class(add_perms=PERM)(user=self.denied)
        for name in ('select', 'multiple', 'tree', 'treemultiple'):
            form.fields[name].widget.can_add = True
        self.assertButton(form, shown=True)
        form = form_class()(user=self.allowed)
        for name in ('select', 'multiple', 'tree', 'treemultiple'):
            form.fields[name].widget.can_add = False
        self.assertButton(form, shown=False)

    def test_each_form_instance_has_its_own_user(self):
        cls = form_class(add_perms=PERM)
        allowed, denied = cls(user=self.allowed), cls(user=self.denied)
        self.assertButton(allowed, shown=True)
        self.assertButton(denied, shown=False)

    def test_the_old_mixin_name_still_works(self):
        self.assertIs(UserScopedUploadsMixin, UserBoundWidgetsMixin)


class TreeTemplateTests(AddPermissionTestCase):

    def test_the_tree_button_opens_its_modal_with_bootstrap_5(self):
        html = TreeSelectWithAdd(attrs=dict(ADD)).render('tree', None)
        self.assertIn('data-bs-toggle="modal"', html)
        self.assertNotIn('data-toggle=', html)


class FilteredSelectMultipleAddTests(AddPermissionTestCase):

    def render(self, user, **kwargs):
        widget = FilteredSelectMultiple(add_url='/create/', **kwargs)
        widget.bind_user(user)
        return widget.render('languages', None, attrs={'id': 'id_languages'})

    def test_add_perms_limit_the_create_button(self):
        self.assertIn('data-addurl="/create/"',
                      self.render(self.allowed, add_perms=PERM))
        rendered = self.render(self.denied, add_perms=PERM)
        self.assertNotIn('data-addurl', rendered)
        self.assertNotIn('id="id_languages_modal"', rendered)

    def test_without_add_perms_nothing_changes(self):
        self.assertIn('data-addurl="/create/"', self.render(None))
