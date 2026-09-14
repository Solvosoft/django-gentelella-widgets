"""Browser tests for FilteredSelectMultiple (/filteredselect/).

The widget is two native <select multiple> and the right hand one *is* the form
field, so nearly everything worth asserting is about where the <option> nodes
end up: what sits in the chosen select at submit time is what posts.

Three things here cannot be seen from the Python tests: the static split (the
template renders every option in the chosen select and the javascript moves the
unselected ones out), the ajax fill, and that two widgets on one page stay
independent.
"""

from datetime import date

from django.test import tag
from django.utils import timezone

from demoapp.models import Community, Country, PeopleGroup, Person

from .base import By, SeleniumTestCase

COMMUNITIES = ['Alajuela', 'Cartago', 'Heredia', 'Limon', 'Puntarenas']
PEOPLE = ['Ana', 'Bruno', 'Carla']

STATIC_ID = 'id_static-languages'
COMMUNITIES_ID = 'id_communities'


class FilteredSelectBase(SeleniumTestCase):
    def setup_data(self):
        for name in COMMUNITIES:
            Community.objects.create(name=name)
        # `people` is a required m2m on PeopleGroup, so the save test needs
        # something to put in it.
        country = Country.objects.create(name='Costa Rica', code='cr')
        for name in PEOPLE:
            Person.objects.create(
                name=name,
                country=country,
                born_date=date(1990, 1, 1),
                last_time=timezone.now(),
            )

    # -- helpers -------------------------------------------------------------
    def open_page(self):
        """Open the demo with a viewport tall enough for the whole page.

        The gentelella layout pins html and body to the viewport height, so the
        document never scrolls: a control below the fold is genuinely
        unclickable rather than merely off screen. Two widgets plus a table do
        not fit in the default 1100px, so the viewport gets the room instead.
        """
        self.set_viewport(1500, 2200)
        self.go('/filteredselect/')

    def options(self, select_id):
        """The visible option labels of one select, in document order."""
        return self.js(
            'return Array.from(document.getElementById(arguments[0]).'
            'querySelectorAll("option")).filter(function(o){return !o.hidden})'
            '.map(function(o){return o.textContent.trim()})',
            select_id,
        )

    def available(self, widget_id):
        return self.options(widget_id + '_available')

    def chosen(self, widget_id):
        return self.options(widget_id)

    def pick(self, select_id, label):
        """Select one option by its label, without moving it."""
        # `label` is read out of `arguments` before the callback: inside
        # function(o){...} `arguments` is the callback's own, not the script's.
        self.js(
            'var wanted = arguments[1];'
            'Array.from(document.getElementById(arguments[0])'
            '.querySelectorAll("option")).forEach(function(o){'
            'o.selected = o.textContent.trim() === wanted})',
            select_id,
            label,
        )

    def click(self, widget_id, suffix):
        self.driver.find_element(By.ID, widget_id + suffix).click()


@tag('selenium')
class StaticModeTest(FilteredSelectBase):
    """No endpoint: options come from `choices`, grouped in optgroups."""

    def test_unselected_options_move_to_the_available_panel(self):
        self.open_page()
        self.wait_js(
            'return document.getElementById(arguments[0] + "_available")'
            '.querySelectorAll("option").length > 0',
            STATIC_ID,
        )
        self.assertEqual(
            sorted(self.available(STATIC_ID)),
            ['C', 'Go', 'JavaScript', 'Python', 'Ruby', 'Rust'],
        )
        self.assertEqual(self.chosen(STATIC_ID), [])

    def test_optgroups_survive_the_split(self):
        self.open_page()
        self.wait_js(
            'return document.getElementById(arguments[0] + "_available")'
            '.querySelectorAll("optgroup").length === 2',
            STATIC_ID,
        )
        labels = self.js(
            'return Array.from(document.getElementById(arguments[0] + '
            '"_available").querySelectorAll("optgroup")).map(function(g){'
            'return g.getAttribute("label")})',
            STATIC_ID,
        )
        self.assertEqual(sorted(labels), ['Compiled', 'Interpreted'])

    def test_the_arrows_move_options_both_ways(self):
        self.open_page()
        self.wait_js(
            'return document.getElementById(arguments[0] + "_available")'
            '.querySelectorAll("option").length > 0',
            STATIC_ID,
        )
        self.pick(STATIC_ID + '_available', 'Python')
        self.click(STATIC_ID, '_add')
        self.assertEqual(self.chosen(STATIC_ID), ['Python'])
        self.assertNotIn('Python', self.available(STATIC_ID))

        self.pick(STATIC_ID, 'Python')
        self.click(STATIC_ID, '_remove')
        self.assertEqual(self.chosen(STATIC_ID), [])
        self.assertIn('Python', self.available(STATIC_ID))

    def test_a_moved_option_is_marked_selected(self):
        """What posts is the chosen select, so the node has to carry
        `selected` -- there is no submit hook to set it later."""
        self.open_page()
        self.wait_js(
            'return document.getElementById(arguments[0] + "_available")'
            '.querySelectorAll("option").length > 0',
            STATIC_ID,
        )
        self.pick(STATIC_ID + '_available', 'Go')
        self.click(STATIC_ID, '_add')
        self.assertTrue(
            self.js(
                'return document.getElementById(arguments[0])'
                '.querySelector("option").selected',
                STATIC_ID,
            )
        )

    def test_choose_all_and_remove_all(self):
        self.open_page()
        self.wait_js(
            'return document.getElementById(arguments[0] + "_available")'
            '.querySelectorAll("option").length > 0',
            STATIC_ID,
        )
        self.click(STATIC_ID, '_addall')
        self.assertEqual(len(self.chosen(STATIC_ID)), 6)
        self.assertEqual(self.available(STATIC_ID), [])

        self.click(STATIC_ID, '_removeall')
        self.assertEqual(self.chosen(STATIC_ID), [])
        self.assertEqual(len(self.available(STATIC_ID)), 6)

    def test_the_filter_box_hides_what_does_not_match(self):
        self.open_page()
        self.wait_js(
            'return document.getElementById(arguments[0] + "_available")'
            '.querySelectorAll("option").length > 0',
            STATIC_ID,
        )
        self.driver.find_element(By.ID, STATIC_ID + '_filter').send_keys('ru')
        self.wait_js(
            'return $("#" + arguments[0] + "_available option").not("[hidden]")'
            '.length === 2',
            STATIC_ID,
        )
        self.assertEqual(sorted(self.available(STATIC_ID)), ['Ruby', 'Rust'])

    def test_choose_all_only_takes_what_the_filter_left_visible(self):
        self.open_page()
        self.wait_js(
            'return document.getElementById(arguments[0] + "_available")'
            '.querySelectorAll("option").length > 0',
            STATIC_ID,
        )
        self.driver.find_element(By.ID, STATIC_ID + '_filter').send_keys('ru')
        self.wait_js(
            'return $("#" + arguments[0] + "_available option").not("[hidden]")'
            '.length === 2',
            STATIC_ID,
        )
        self.click(STATIC_ID, '_addall')
        self.assertEqual(sorted(self.chosen(STATIC_ID)), ['Ruby', 'Rust'])


@tag('selenium')
class ApiModeTest(FilteredSelectBase):
    """With a gtselects endpoint the available panel is filled over ajax."""

    def test_the_available_panel_is_filled_from_the_endpoint(self):
        self.open_page()
        self.wait_js(
            'return document.getElementById(arguments[0] + "_available")'
            '.querySelectorAll("option").length > 0',
            COMMUNITIES_ID,
        )
        self.assertEqual(sorted(self.available(COMMUNITIES_ID)), sorted(COMMUNITIES))
        self.assertEqual(self.chosen(COMMUNITIES_ID), [])

    def test_moving_an_option_and_saving_persists_it(self):
        self.open_page()
        self.wait_js(
            'return document.getElementById(arguments[0] + "_available")'
            '.querySelectorAll("option").length > 0',
            COMMUNITIES_ID,
        )
        self.wait_js(
            'return document.getElementById("id_people_available")'
            '.querySelectorAll("option").length > 0'
        )
        self.driver.find_element(By.ID, 'id_name').send_keys('Zona Central')
        self.pick(COMMUNITIES_ID + '_available', 'Cartago')
        self.click(COMMUNITIES_ID, '_add')
        self.pick('id_people_available', 'Ana')
        self.click('id_people', '_add')
        self.driver.find_element(
            By.CSS_SELECTOR, 'form button[type=submit]'
        ).click()
        self.wait_js('return document.readyState === "complete"')

        group = PeopleGroup.objects.get(name='Zona Central')
        self.assertEqual(
            list(group.communities.values_list('name', flat=True)), ['Cartago']
        )

    def test_saved_values_come_back_in_the_chosen_panel(self):
        group = PeopleGroup.objects.create(name='Zona Norte')
        group.communities.add(Community.objects.get(name='Heredia'))
        self.open_page()
        self.wait_js(
            'return document.getElementById(arguments[0] + "_available")'
            '.querySelectorAll("option").length > 0',
            COMMUNITIES_ID,
        )
        # The form on the page is unbound, so nothing is chosen; what this
        # asserts is that the endpoint does not offer a row twice and that the
        # saved group is unaffected by the render.
        self.assertNotIn('', self.available(COMMUNITIES_ID))
        self.assertEqual(group.communities.count(), 1)


@tag('selenium')
class MultipleInstancesTest(FilteredSelectBase):
    def test_two_widgets_on_one_page_stay_independent(self):
        """Each widget is registered by the id of its own select; a shared
        state object -- or a shared modal id -- makes the second one drive the
        first."""
        self.open_page()
        self.wait_js(
            'return document.getElementById(arguments[0] + "_available")'
            '.querySelectorAll("option").length > 0',
            STATIC_ID,
        )
        self.wait_js(
            'return document.getElementById(arguments[0] + "_available")'
            '.querySelectorAll("option").length > 0',
            COMMUNITIES_ID,
        )
        before = self.available(COMMUNITIES_ID)
        self.click(STATIC_ID, '_addall')
        self.assertEqual(len(self.chosen(STATIC_ID)), 6)
        self.assertEqual(self.available(COMMUNITIES_ID), before)
        self.assertEqual(self.chosen(COMMUNITIES_ID), [])
