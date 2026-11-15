"""A CRUD list over a model without Meta.ordering is paginated in pk order."""

import warnings
from datetime import date

from django.core.paginator import UnorderedObjectListWarning
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from demoapp.models import Country, Person
from djgentelella.cruds.utils import crud_url_name


class CrudOrderingTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        country = Country.objects.create(name='Costa Rica')
        cls.people = [Person.objects.create(
            name='Person %d' % n, country=country, born_date=date(2000, 1, 1),
            last_time=timezone.now()) for n in range(3)]

    def test_an_unordered_model_is_listed_by_pk_without_a_warning(self):
        url = reverse(crud_url_name(Person, 'list'))
        with warnings.catch_warnings():
            warnings.simplefilter('error', UnorderedObjectListWarning)
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['object_list']), self.people)
