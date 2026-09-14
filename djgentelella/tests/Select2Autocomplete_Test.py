from django.test import RequestFactory, TestCase

from demoapp.models import Community
from djgentelella.views.select2autocomplete import BaseSelect2View


class CommunityLookup(BaseSelect2View):
    model = Community
    fields = ['name']


class CommunityExcludingLookup(BaseSelect2View):
    model = Community
    fields = ['name']
    exclude_selected = True


class GPaginatorLargePage(CommunityLookup.pagination_class):
    page_size = 50


CommunityLookup.pagination_class = GPaginatorLargePage
CommunityExcludingLookup.pagination_class = GPaginatorLargePage


class ExcludeSelectedTest(TestCase):
    """`selected` tells the endpoint what the widget already holds.

    By default those rows still come back, flagged, because the autocomplete
    widgets need them to rebuild their <option> nodes. `exclude_selected` is
    the opt-in that drops them instead, so a page never comes back full of
    entries the browser is only going to hide.
    """

    @classmethod
    def setUpTestData(cls):
        cls.people = [
            Community.objects.create(name='Community %d' % i) for i in range(5)
        ]

    def get(self, view, **params):
        request = RequestFactory().get('/gtapis/community/', params)
        response = view.as_view({'get': 'list'})(request)
        response.render()
        return response.data

    def test_selected_rows_come_back_flagged_by_default(self):
        chosen = self.people[0]
        data = self.get(CommunityLookup, selected=str(chosen.pk))
        ids = [row['id'] for row in data['results']]
        self.assertIn(chosen.pk, ids)
        flagged = [row for row in data['results'] if row['id'] == chosen.pk][0]
        self.assertTrue(flagged['selected'])

    def test_exclude_selected_drops_them(self):
        chosen = self.people[:2]
        data = self.get(
            CommunityExcludingLookup,
            selected=','.join(str(person.pk) for person in chosen),
        )
        ids = [row['id'] for row in data['results']]
        for person in chosen:
            self.assertNotIn(person.pk, ids)
        self.assertEqual(len(ids), len(self.people) - len(chosen))

    def test_exclude_selected_is_a_noop_without_selected(self):
        data = self.get(CommunityExcludingLookup)
        self.assertEqual(len(data['results']), len(self.people))

    def test_exclude_selected_still_honours_term(self):
        data = self.get(
            CommunityExcludingLookup,
            term='Community 1',
            selected=str(self.people[1].pk),
        )
        self.assertEqual(data['results'], [])
