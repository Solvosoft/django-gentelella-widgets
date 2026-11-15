import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from demoapp.dynamic_actions.forms import DynamicContactForm
from djgentelella.forms.dynamic import serialize_rules


class DemoCalcTotalTest(SimpleTestCase):
    """The server total of the demo with whatever the browser sends."""

    def calc(self, **data):
        return DynamicContactForm().calc_total(data)

    def test_regular_values(self):
        self.assertEqual(self.calc(quantity='3', price='10', discount='10'),
                         {'total': '27.00'})
        self.assertEqual(self.calc(quantity='2', price='1,5'), {'total': '3.00'})

    def test_garbage_nan_and_infinity_count_as_zero(self):
        for value in ('abc', 'NaN', 'sNaN', 'Infinity', '-Infinity', '', None):
            with self.subTest(value):
                self.assertEqual(self.calc(quantity=value, price='1'),
                                 {'total': '0.00'})
                self.assertEqual(self.calc(quantity='1', price='1', discount=value),
                                 {'total': '1.00'})

    def test_a_huge_number_is_a_validation_error(self):
        for value in ('1e999999', '1e12', '99999999999999'):
            with self.subTest(value):
                with self.assertRaises(ValidationError):
                    self.calc(quantity=value, price='1')


class DemoCalcTotalEndpointTest(TestCase):
    def test_huge_quantity_is_a_400_not_a_500(self):
        user = get_user_model().objects.create_user('calc', password='x')
        self.client.force_login(user)
        form = DynamicContactForm()
        rules = serialize_rules(form, form.get_dynamic_actions())
        token = rules[1]['actions'][0]['server']
        response = self.client.post(
            reverse('gt-dynamic-action'),
            json.dumps({'token': token,
                        'data': {'quantity': '1e999999', 'price': '1'}}),
            content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.json())


class DemoSendCopyTest(SimpleTestCase):
    def test_the_checkbox_rule_and_its_server_check(self):
        form = DynamicContactForm()
        rules = serialize_rules(form, form.get_dynamic_actions())
        self.assertIn({'when': ['send_copy'], 'trigger': 'is_checked',
                       'actions': [{'action': 'show', 'fields': ['copy_email']},
                                   {'action': 'require', 'fields': ['copy_email']}]},
                      rules)
        form = DynamicContactForm({'send_copy': 'on'})
        form.is_valid()
        self.assertIn('copy_email', form.errors)
