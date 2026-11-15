"""Browser tests of the flow demos: the expense approval, in Python and in
JSON, driven through its pages -- the transition button, the task inbox and
the task page, the payment signal -- and the runtime diagram.

The unit tests cover the engine; what is checked here is that the pages a
user goes through wire it together.
"""

from django.contrib.auth.models import Group
from django.test import tag

from demoapp.flowdemos.seed import create_users, load_expense_definition, task_of
from demoapp.models import ExpenseReport
from djgentelella.flows import get_flow
from .base import By, EC, SeleniumTestCase


@tag('selenium')
class ExpenseDemoTest(SeleniumTestCase):

    def setup_data(self):
        self.ana, self.beto, self.carla = create_users()
        load_expense_definition()
        self.expenses = {}
        for flow_name in ('demoapp.ExpenseFlow', 'demoapp.expenses_json'):
            obj = ExpenseReport.objects.create(
                title='Conference %s' % flow_name.split('.')[1], amount=2000,
                requester=self.user, manager=self.user, flow_name=flow_name)
            get_flow(flow_name).start(obj, self.user)
            self.expenses[flow_name] = obj

    def click(self, selector):
        element = self.wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, selector)))
        self.driver.execute_script('arguments[0].scrollIntoView({block: "center"})',
                                   element)
        element.click()

    def run_expense(self, flow_name, slug):
        obj = self.expenses[flow_name]
        flow = get_flow(flow_name)
        self.go('/flowdemos/%s/' % slug)
        self.assertIn(obj.title, self.driver.page_source)
        # The Submit button of {% flow_status %}, then its transition page.
        self.click('a[href*="/run/submit/%d/"]' % obj.pk)
        self.wait.until(EC.presence_of_element_located(
            (By.NAME, 'flow_comment-comment')))
        self.driver.find_element(By.NAME, 'flow_comment-comment').send_keys('Trip')
        self.click('form button[type=submit].btn-primary')
        self.wait.until(lambda driver: flow.state(obj) == 'review')

        # The manager's task, from the task inbox.
        self.go('/flows/inbox/?flow=%s' % flow_name)
        self.click('tr[data-task="%d"] a.btn' % task_of(obj, self.user).pk)
        self.click('.gt-task-complete button[value="approve"]')
        self.wait.until(EC.url_contains('/flows/inbox/'))
        self.assertEqual(flow.state(obj), 'review')  # finance is missing

        # Finance (carla) decides outside the browser; the page then pays it.
        task_of(obj, self.carla).complete(self.carla, 'approve')
        self.assertEqual(flow.state(obj), 'payment')
        self.go('/flowdemos/%s/' % slug)
        self.click('.gt-demo-pay')
        self.wait.until(lambda driver: flow.state(obj) == 'closed')
        obj.refresh_from_db()
        self.assertTrue(obj.paid)

        # The instance's diagram: done activities marked, none failed.
        self.go('/flows/%s/object/%d/' % (flow_name, obj.pk))
        diagram = self.driver.find_element(By.CSS_SELECTOR, 'svg.gt-flow-diagram')
        completed = diagram.find_elements(
            By.CSS_SELECTOR, 'g.gt-flow-node[data-status="completed"]')
        states = {node.get_attribute('data-state') for node in completed}
        self.assertTrue({'draft', 'review', 'finance_review', 'manager_review',
                         'payment'} <= states, states)
        self.assertEqual(diagram.find_elements(
            By.CSS_SELECTOR, 'g.gt-flow-node[data-status="error"]'), [])

    def test_python_flow(self):
        self.run_expense('demoapp.ExpenseFlow', 'expenses')

    def test_json_flow(self):
        self.run_expense('demoapp.expenses_json', 'expenses-json')

    def test_task_inbox_filters(self):
        Group.objects.get(name='Finance').user_set.add(self.user)
        flow = get_flow('demoapp.ExpenseFlow')
        flow.run(self.expenses['demoapp.ExpenseFlow'], 'submit', self.user)
        self.go('/flows/inbox/')
        rows = self.driver.find_elements(By.CSS_SELECTOR,
                                         'table.gt-task-inbox tbody tr')
        self.assertEqual(len(rows), 2)
        self.driver.find_element(By.ID, 'task-filter-priority').send_keys('2')
        self.click('.gt-task-filters button[type=submit]')
        self.wait.until(EC.url_contains('priority=2'))
        rows = self.driver.find_elements(By.CSS_SELECTOR,
                                         'table.gt-task-inbox tbody tr')
        self.assertEqual(len(rows), 2)  # both review tasks are priority 2
        self.go('/flows/inbox/?due=none')
        self.assertIn('Approve the expense', self.driver.page_source)
        self.assertNotIn('Finance: approve', self.driver.page_source)
