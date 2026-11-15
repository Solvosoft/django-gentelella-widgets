"""Browser test of a human task with a form (``human_task.form``): the task
page shows the form above the outcome buttons, an invalid value keeps the
task open with the error on the page, and a valid one moves the flow and
writes the variables."""

from django import forms
from django.contrib.auth.models import Group
from django.test import tag

from demoapp.models import Country
from djgentelella.flows import get_flow, publish_definition, register_task_form
from djgentelella.flows.models import Task
from .base import By, EC, SeleniumTestCase


@register_task_form('demoapp.selenium.check')
class CheckForm(forms.Form):
    score = forms.IntegerField(min_value=1, max_value=5)
    note = forms.CharField(required=False)


FLOW = {
    'schema_version': 2, 'name': 'demoapp.selenium_check', 'model': 'demoapp.Country',
    'initial': 'draft',
    'states': [
        {'id': 'draft', 'type': 'state'},
        {'id': 'check', 'type': 'human_task', 'title': 'Check {{ object }}',
         'groups': ['Selenium checkers'], 'form': 'demoapp.selenium.check',
         'outcomes': {'approve': 'done', 'reject': 'draft'}},
        {'id': 'done', 'type': 'state'},
    ],
    'transitions': [{'name': 'submit', 'source': 'draft', 'target': 'check'}],
}


@tag('selenium')
class TaskFormTest(SeleniumTestCase):

    def setup_data(self):
        self.user.groups.add(Group.objects.create(name='Selenium checkers'))
        publish_definition(FLOW)
        self.country = Country.objects.create(name='Uruguay')
        self.flow = get_flow('demoapp.selenium_check')
        self.flow.run(self.country, 'submit', self.user)
        self.task = Task.objects.get(activity='check')

    def click(self, selector):
        element = self.wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, selector)))
        self.driver.execute_script('arguments[0].scrollIntoView({block: "center"})',
                                   element)
        element.click()

    def test_the_form_is_validated_and_written_to_the_variables(self):
        self.go('/flows/tasks/%d/' % self.task.pk)
        score = self.wait.until(EC.presence_of_element_located(
            (By.NAME, 'task-score')))
        score.clear()
        score.send_keys('9')
        # The browser's own max= check would stop the post: the server's is
        # the one under test.
        self.driver.execute_script("arguments[0].removeAttribute('max')", score)
        self.click('.gt-task-complete button[value="approve"]')
        self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, '.gt-task-form .errorlist')))
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_open)

        score = self.driver.find_element(By.NAME, 'task-score')
        score.clear()
        score.send_keys('4')
        self.driver.find_element(By.NAME, 'task-note').send_keys('<b>fine</b>')
        self.click('.gt-task-complete button[value="approve"]')
        self.wait.until(EC.url_contains('/flows/inbox/'))
        instance = self.flow.get_instance(self.country, create=False)
        self.assertEqual(instance.state, 'done')
        self.assertEqual((instance.variables['score'], instance.variables['note']),
                         (4, '<b>fine</b>'))
