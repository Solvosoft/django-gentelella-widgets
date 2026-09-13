"""Browser tests for the chained autocomplete selects (/abcde/create/).

Two behaviours live here that only exist in the browser:

* ``data-autoresetchildren`` -- changing a level of the chain empties every
  level below it, so a value that no longer belongs to its parent cannot
  survive the change.
* already chosen entries must not keep showing in the dropdown of a multiple
  select. select2 4.1 dropped the ``hideSelected`` option 3.x had, so the
  library reimplements it.
"""

from django.test import tag

from demoapp.models import A, B, C, D, E

from .base import By, SeleniumTestCase


class RelatedSelectsBase(SeleniumTestCase):
    def setup_data(self):
        for index in range(2):
            a = A.objects.create(display='A%d' % index)
            b = B.objects.create(display='B%d' % index, a=a)
            c = C.objects.create(display='C%d' % index, b=b)
            d = D.objects.create(display='D%d' % index, c=c)
            E.objects.create(display='E%d' % index, d=d)

    # -- helpers -------------------------------------------------------------
    def set_value(self, field_id, value):
        """Pick a value the way the widget itself does: append the option and
        let select2 know. Driving the dropdown by hand would test select2."""
        self.js(
            'var select = $("#" + arguments[0]);'
            'if (!select.find("option[value=\'" + arguments[1] + "\']").length){'
            '  select.append(new Option(arguments[2], arguments[1], true, true));'
            '}'
            'select.val(arguments[1]);'
            'select.trigger("change");'
            'select.trigger({type: "select2:select",'
            '                params: {data: {id: arguments[1]}}});',
            field_id,
            str(value),
            str(value),
        )

    def value_of(self, field_id):
        # A multiple with nothing picked answers null; a single one answers the
        # empty string, because select2 falls back to the blank <option>. Both
        # mean "no value".
        return self.js(
            'var v = $("#" + arguments[0]).val();'
            'if (v === null) return [];'
            'if (!Array.isArray(v)) v = [v];'
            'return v.filter(function(x){return x !== "" && x !== null});',
            field_id,
        )

    def open_dropdown(self, field_id):
        self.js('$("#" + arguments[0]).select2("open")', field_id)

    def dropdown_options(self):
        self.wait_js(
            'return document.querySelectorAll('
            '".select2-results__option").length > 0'
        )
        return self.js(
            'return Array.from(document.querySelectorAll('
            '".select2-results__option")).filter(function(o){'
            '  return o.offsetParent !== null;'
            '}).map(function(o){return o.textContent.trim()})'
        )


@tag('selenium')
class AutoResetChildrenTest(RelatedSelectsBase):
    """ABCDEGroupForm sets data-autoresetchildren on every level."""

    def test_changing_a_parent_empties_every_level_below_it(self):
        self.go('/abcde/create/')
        self.assert_widget_ready('#id_b')
        b = B.objects.first()
        c = C.objects.first()
        self.set_value('id_b', b.pk)
        self.set_value('id_c', c.pk)
        self.assertEqual(self.value_of('id_c'), [str(c.pk)])

        # a is the head of the chain, so c has to go even though it is two
        # levels down -- the cascade is not just the immediate child.
        self.set_value('id_a', A.objects.first().pk)
        self.wait_js(
            'var v = $("#id_c").val(); return v === null || v.length === 0;',
            message='id_c was not reset when id_a changed',
        )
        self.assertEqual(self.value_of('id_b'), [])
        self.assertEqual(self.value_of('id_c'), [])

    def test_the_bound_values_survive_the_page_load(self):
        """The reset listens to select2's own select/unselect events, not to
        `change`: the chain triggers `change` while it is still initialising,
        and reacting to that would wipe an edit form on load."""
        chain_e = E.objects.first()
        self.go('/abcde/create/')
        self.assert_widget_ready('#id_e')
        self.set_value('id_e', chain_e.pk)
        self.go('/abcde/create/')
        self.assert_widget_ready('#id_e')
        # Nothing was reset by the load itself; the form simply comes up empty.
        self.assertEqual(self.value_of('id_e'), [])


@tag('selenium')
class HideSelectedTest(RelatedSelectsBase):
    """An entry the user already chose must leave the dropdown."""

    def test_a_chosen_entry_leaves_the_multiple_dropdown(self):
        self.go('/abcde/create/')
        self.assert_widget_ready('#id_a')
        first = A.objects.first()
        self.open_dropdown('id_a')
        self.assertIn(first.display, self.dropdown_options())
        self.js('$("#id_a").select2("close")')

        self.set_value('id_a', first.pk)
        self.open_dropdown('id_a')
        self.assertNotIn(first.display, self.dropdown_options())

    def test_the_dropdown_carries_the_hide_selected_class(self):
        """The css rule is what does it for selects whose options come from
        the DOM instead of an endpoint."""
        self.go('/abcde/create/')
        self.assert_widget_ready('#id_a')
        self.open_dropdown('id_a')
        self.assertTrue(
            self.js(
                'return document.querySelectorAll('
                '".select2-dropdown.gt-hide-selected").length > 0'
            )
        )

    def test_single_selects_keep_showing_their_value(self):
        """Only multiples hide the chosen entry: on a single select the value
        has to stay visible or the user cannot see what is picked."""
        self.go('/abcde/create/')
        self.assert_widget_ready('#id_b')
        self.assertFalse(
            self.js(
                'return $("#id_b").data("select2").$dropdown'
                '.hasClass("gt-hide-selected")'
            )
        )
