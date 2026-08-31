"""The permission management modal: the checkboxes have to be there to tick.

iCheck worked by hiding the real ``<input>`` and drawing its own DOM beside it,
so every template that used it had to hide the input by hand. Commit 92e01ed
replaced iCheck with CSS painted on the native input -- the input *is* the
widget now -- but this template kept its
``style="position: absolute; opacity: 0;"``. The result was a permission tree
with labels and nothing to click: the modal rendered, the categories expanded,
and there was no way to grant a permission.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import tag

from djgentelella.models import PermissionsCategoryManagement
from .base import SeleniumTestCase

PAGE = '/pgroup/'


@tag('selenium')
class PermissionModalTest(SeleniumTestCase):

    def setup_data(self):
        # The page itself creates these through
        # {% get_or_create_permission_context %}, but only for permissions that
        # already exist; creating them here keeps the test independent of the
        # demo's migration order.
        for codename, name in (('change_peoplegroup', 'Edit group'),
                               ('add_peoplegroup', 'Create group')):
            permission = Permission.objects.filter(
                codename=codename,
                content_type__app_label='demoapp').first()
            if permission:
                PermissionsCategoryManagement.objects.get_or_create(
                    url_name='pgroup-%s' % codename.split('_')[0],
                    permission=permission,
                    defaults={'name': name, 'category': 'Group'})

    def open_modal(self):
        self.go(PAGE)
        self.wait_js(
            "return document.querySelector('#btn_perms') !== null;",
            message='the permission button is not on the page')
        self.js("document.querySelector('#btn_perms').click();")
        self.wait_js(
            "const m = document.querySelector('#permission_modal');"
            "return m && m.classList.contains('show')"
            "       && document.querySelectorAll("
            "            '#permissionbody input[name=permission]').length > 0;",
            message='the permission tree never loaded')
        # Every category starts collapsed; open them so the checkboxes are laid
        # out rather than inside a display:none block.
        self.js("document.querySelectorAll('#permissionbody .collapse')"
                "  .forEach(c => c.classList.add('show'));")
        self.settle()

    def boxes(self):
        return self.js(
            "return Array.from(document.querySelectorAll("
            "  '#permissionbody input[name=permission]')).map(e => '#' + e.id);")

    def test_every_permission_offers_a_checkbox_to_tick(self):
        self.open_modal()
        found = self.boxes()
        self.assertTrue(found, 'the tree lists no permissions at all')
        for css in found:
            self.assert_reachable(css, message='permission checkbox')

    def test_the_checkbox_is_drawn_and_not_hidden_off_the_layout(self):
        """What actually broke: the input was still hidden for iCheck's sake."""
        self.open_modal()
        css = self.boxes()[0]
        state = self.js(
            'const e = document.querySelector(arguments[0]);'
            'const c = getComputedStyle(e);'
            'return [c.opacity, c.position, c.appearance,'
            '        e.getBoundingClientRect().width];', css)
        self.assertNotEqual(
            state[0], '0',
            'the checkbox is transparent: nothing draws it now that iCheck is '
            'gone, so the tree has labels and nothing to tick')
        self.assertGreater(
            state[3], 0, 'the checkbox has no width')
        self.assertEqual(
            state[2], 'none',
            'the checkbox is not being painted by checks.css (appearance is '
            f'{state[2]!r}, so the .gt-check class is not in effect)')

    def test_ticking_a_box_registers(self):
        """The point of the control: clicking it selects that permission."""
        self.open_modal()
        css = self.boxes()[0]
        self.js('document.querySelector(arguments[0]).click();', css)
        self.assertTrue(
            self.js('return document.querySelector(arguments[0]).checked;',
                    css),
            'clicking the checkbox did not check it')
        self.assertEqual(
            self.js("return document.querySelectorAll("
                    "  'input[name=permission]:checked').length;"),
            1)

    def test_the_label_toggles_its_own_checkbox(self):
        """`for=` has to point at the input; it is how the text is clickable."""
        self.open_modal()
        css = self.boxes()[0]
        self.js(
            "document.querySelector('label[for=' + JSON.stringify("
            "  document.querySelector(arguments[0]).id) + ']').click();", css)
        self.assertTrue(
            self.js('return document.querySelector(arguments[0]).checked;',
                    css),
            'clicking the label did not tick its checkbox')

    def choose_user(self, user):
        """Pick a user in the select2, the way select2 documents doing it."""
        self.js(
            "const s = $('#select_user');"
            "s.append(new Option(arguments[1], arguments[0], true, true))"
            " .trigger('change');"
            "s.trigger({type: 'select2:select',"
            "           params: {data: {id: arguments[0], text: arguments[1]}}});",
            str(user.pk), user.username)

    def test_ticking_and_saving_grants_the_permission(self):
        """End to end: the modal exists to change what someone may do."""
        User = get_user_model()
        target = User.objects.create_user(
            username='enrique', email='enrique@example.com', password='x')

        self.open_modal()
        self.choose_user(target)
        css = self.boxes()[0]
        permission_id = int(self.js(
            'return document.querySelector(arguments[0]).value;', css))
        self.js('document.querySelector(arguments[0]).click();', css)
        self.js("document.querySelector('#btn_savepermissions').click();")
        self.wait.until(
            lambda d: target.user_permissions.filter(
                pk=permission_id).exists(),
            'saving never granted the permission')

    def test_choosing_a_user_shows_the_permissions_they_already_have(self):
        """The boxes have to reflect stored state, which is what iCheck needed
        an imperative `update` call for and the native input does on its own."""
        User = get_user_model()
        target = User.objects.create_user(
            username='rosa', email='rosa@example.com', password='x')

        self.open_modal()
        first = self.boxes()[0]
        permission_id = int(self.js(
            'return document.querySelector(arguments[0]).value;', first))
        target.user_permissions.add(Permission.objects.get(pk=permission_id))

        self.choose_user(target)
        self.wait_js(
            'return document.querySelector(arguments[0]).checked;', first,
            message='the stored permission was not ticked for the user')

    def test_the_page_reports_no_javascript_error(self):
        self.driver.get_log('browser')
        self.open_modal()
        severe = [entry['message'] for entry in self.driver.get_log('browser')
                  if entry['level'] == 'SEVERE']
        self.assertEqual(severe, [])
