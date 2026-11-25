"""The kanban board of a flow (``flow_kanban``) in a browser: the demo's help
desk board (``demoapp/gtdesign/ticket_kanban.json``), cards dragged from one
column to another, a refused move, and the "Move to" menu with a form."""
import json

from django.contrib.auth.models import Group
from django.test import tag
from selenium.webdriver.common.action_chains import ActionChains

from demoapp.models import SupportTicket
from djgentelella.designs import engine, publishing
from djgentelella.flows import get_flow
from djgentelella.flows.models import FlowTransitionLog
from djgentelella.tests.DesignsData_Test import DEMO_DESIGNS

from .base import EC, By, SeleniumTestCase

FLOW = 'demoapp.TicketFlow'
BOARD = '[data-gtdesign="tickets"]'

# The events a browser fires for an HTML5 drag and drop, with one
# DataTransfer, dispatched on the same elements: the test reads the columns
# marked between dragstart and drop, which a WebDriver drag cannot stop at
# (test_a_real_mouse_drag does the same move with WebDriver's own).
DRAG = """
var card = arguments[0], column = arguments[1];
var data = new DataTransfer();
function fire(target, type) {
    var event = new DragEvent(type, {bubbles: true, cancelable: true,
                                     dataTransfer: data});
    target.dispatchEvent(event);
}
fire(card, 'dragstart');
var marked = Array.prototype.map.call(
    document.querySelectorAll('.gtkanban-column'), function (item) {
        return [item.getAttribute('data-state'), item.className];
    });
fire(column, 'dragenter');
fire(column, 'dragover');
fire(column, 'drop');
fire(card, 'dragend');
return marked;
"""


@tag('selenium')
class FlowKanbanTest(SeleniumTestCase):

    def setup_data(self):
        engine.clear_cache()
        with open(DEMO_DESIGNS / 'ticket_kanban.json') as stream:
            _page, errors = publishing.publish(json.load(stream))
        self.assertEqual(errors, [])
        Group.objects.get_or_create(name='Support')  # the triage assigns to it
        self.flow = get_flow(FLOW)
        self.printer = self.ticket('The printer does not print')
        self.vpn = self.ticket('The VPN is down')
        self.flow.run(self.vpn, 'start', self.user)

    def ticket(self, subject):
        obj = SupportTicket.objects.create(subject=subject, description=subject,
                                           priority='normal', reporter=self.user)
        self.flow.evaluate(obj, self.user)  # triage: into the queue
        return obj

    def card(self, obj):
        return self.driver.find_element(
            By.CSS_SELECTOR, '%s .gtkanban-card[data-pk="%d"]' % (BOARD, obj.pk))

    def column(self, state):
        return self.driver.find_element(
            By.CSS_SELECTOR, '%s .gtkanban-column[data-state="%s"]' % (BOARD, state))

    def column_of(self, obj):
        return self.js(
            "var card = document.querySelector("
            "  '.gtkanban-card[data-pk=\"' + arguments[0] + '\"]');"
            "return card && !card.classList.contains('gtkanban-pending') ? "
            "  card.closest('.gtkanban-column').getAttribute('data-state') : null;",
            str(obj.pk))

    def open_board(self):
        self.go('/designs/tickets-board/')
        self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, BOARD + ' .gtkanban-card')))

    def drag(self, obj, state):
        return dict(self.js(DRAG, self.card(obj), self.column(state)))

    def message(self):
        return self.driver.find_element(By.CSS_SELECTOR,
                                        BOARD + ' .gtkanban-message').text

    def test_drag_a_card_and_see_it_after_reloading(self):
        self.open_board()
        self.assertEqual(self.column_of(self.printer), 'queued')
        marked = self.drag(self.printer, 'in_progress')
        # When the drag starts, the columns it may go to are marked.
        self.assertIn('gtkanban-allowed', marked['in_progress'])
        self.assertIn('gtkanban-forbidden', marked['closed'])
        self.wait.until(lambda d: self.column_of(self.printer) == 'in_progress',
                        'the card never landed in "In progress"')
        self.wait.until(lambda d: self.message(), 'no message after the move')
        self.assertEqual(self.flow.state(self.printer), 'in_progress')
        self.assertTrue(FlowTransitionLog.objects.filter(
            transition='start', instance__object_id=str(self.printer.pk)).exists())
        self.open_board()
        self.assertEqual(self.column_of(self.printer), 'in_progress')

    def test_a_real_mouse_drag(self):
        """The same move with WebDriver's own drag and drop, when the browser
        runs it (it depends on the Chrome version); otherwise skipped."""
        self.open_board()
        ActionChains(self.driver).drag_and_drop(
            self.card(self.printer), self.column('in_progress')).perform()
        try:
            self.wait.until(lambda d: self.column_of(self.printer) == 'in_progress')
        except Exception:
            self.skipTest('this chromedriver does not fire HTML5 drag events')
        self.assertEqual(self.flow.state(self.printer), 'in_progress')

    def test_a_forbidden_move_puts_the_card_back(self):
        self.open_board()
        self.drag(self.printer, 'closed')
        # "No transition goes from <queued> to <closed>.", in the page's
        # language: it names both columns.
        labels = [self.column(state).find_element(By.TAG_NAME, 'h3').text
                  for state in ('queued', 'closed')]
        self.wait.until(lambda d: all(text in self.message() for text in labels),
                        'no reason was shown')
        self.assertTrue(self.driver.find_elements(
            By.CSS_SELECTOR, BOARD + ' .gtkanban-message .alert-danger'))
        self.wait.until(lambda d: self.column_of(self.printer) == 'queued',
                        'the card did not go back to its column')
        self.assertEqual(self.flow.state(self.printer), 'queued')
        self.open_board()
        self.assertEqual(self.column_of(self.printer), 'queued')

    def test_move_to_menu_with_a_form(self):
        self.open_board()
        card = self.card(self.vpn)
        card.find_element(By.CSS_SELECTOR, '.gtkanban-menu .dropdown-toggle').click()
        item = card.find_element(
            By.CSS_SELECTOR, '.gtkanban-move-to[data-target="resolved"]')
        self.wait.until(EC.element_to_be_clickable(item))
        item.click()
        field = self.wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, BOARD + ' .gtkanban-modal [name="flow-resolution"]')))
        submit = self.driver.find_element(
            By.CSS_SELECTOR, BOARD + ' .gtkanban-modal [type="submit"]')
        submit.click()  # empty: the form comes back with its error
        self.wait.until(lambda d: self.driver.find_elements(
            By.CSS_SELECTOR, BOARD + ' .gtkanban-modal .invalid-feedback, '
            + BOARD + ' .gtkanban-modal .errorlist, '
            + BOARD + ' .gtkanban-modal .is-invalid'), 'the form showed no error')
        self.assertEqual(self.flow.state(self.vpn), 'in_progress')
        field = self.driver.find_element(
            By.CSS_SELECTOR, BOARD + ' .gtkanban-modal [name="flow-resolution"]')
        field.send_keys('Restarted the router.')
        self.driver.find_element(
            By.CSS_SELECTOR, BOARD + ' .gtkanban-modal [type="submit"]').click()
        self.wait.until(lambda d: self.column_of(self.vpn) == 'resolved',
                        'the card never landed in "Resolved"')
        self.vpn.refresh_from_db()
        self.assertEqual(self.vpn.resolution, 'Restarted the router.')
        self.assertEqual(self.flow.state(self.vpn), 'resolved')

    def test_the_move_to_menu_opens_with_the_mouse(self):
        """Bootstrap's dropdown, with the Popper of bootstrap.bundle: opened
        by a real click, after the board was loaded more than once (D11 saw
        window.Popper go missing in a run of several tests)."""
        self.go('/')
        self.open_board()
        self.open_board()
        self.assertFalse(self.js(
            'return Array.prototype.some.call(document.scripts, function (s) {'
            '  return /popper(\\.min)?\\.js/.test(s.src); });'),
            'a separate popper.js is loaded')
        self.assertTrue(self.js("return typeof bootstrap.Dropdown === 'function';"))
        card = self.card(self.vpn)
        toggle = card.find_element(By.CSS_SELECTOR, '.gtkanban-menu .dropdown-toggle')
        ActionChains(self.driver).move_to_element(toggle).click().perform()
        menu = card.find_element(By.CSS_SELECTOR, '.gtkanban-menu .dropdown-menu')
        self.wait.until(lambda d: 'show' in menu.get_attribute('class'),
                        'the "Move to" menu did not open')
        self.wait.until(EC.visibility_of(menu))
        self.assertEqual(toggle.get_attribute('aria-expanded'), 'true')
        # Popper placed it: Bootstrap sets data-popper-placement on it.
        self.assertTrue(menu.get_attribute('data-popper-placement'))
        item = card.find_element(By.CSS_SELECTOR,
                                 '.gtkanban-move-to[data-target="resolved"]')
        self.assertTrue(item.is_displayed())
        ActionChains(self.driver).move_to_element(item).click().perform()
        self.wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, BOARD + ' .gtkanban-modal [name="flow-resolution"]')))
