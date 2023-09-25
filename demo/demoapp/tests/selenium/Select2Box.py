import time

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium.webdriver import ActionChains
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from django.urls import reverse
from demoapp.models import Person, Comunity, PeopleGroup, Country, ChoiceItem, PersonGroup
from selenium.webdriver.common.by import By
from datetime import date
from django.utils import timezone

class Select2BoxFormSeleniumTest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super(Select2BoxFormSeleniumTest, cls).setUpClass()

        cls.timeout = 10
        cls.selenium = WebDriver()
        cls.selenium.implicitly_wait(cls.timeout)

    def setUp(self):
        self.country = Country.objects.create(name='Costa Rica')
        self.person = Person.objects.create(name='Person Test', num_children=2, country= self.country, born_date=date.today(), last_time=date.today())
        self.comunity = Comunity.objects.create(name='Comunity Test')
        self.people_g = PeopleGroup.objects.create(name='Group Test', country=self.country)
        self.people_g.people.add(self.person)
        self.people_g.comunities.add(self.comunity)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super(Select2BoxFormSeleniumTest, cls).tearDownClass()

    def test_people_group_showing(self):
        url = self.live_server_url + str(reverse('select2box-group-list'))
        self.selenium.get(url)
        assert 'Group Test' in self.selenium.page_source
        time.sleep(1)

    def test_people_group_edit(self):
        url = self.live_server_url + str(reverse('select2box-group-list'))
        self.selenium.get(url)
        edit_btn = self.selenium.find_element(By.CLASS_NAME, 'btn-outline-warning')
        edit_btn.click()
        time.sleep(2)
        selected_box = self.selenium.find_element(By.ID, 'id_people')
        selected_box_com = self.selenium.find_element(By.ID, 'id_comunities')
        selected_person = selected_box.find_element(By.XPATH, "//option[text()='Person Test']").text
        selected_comunity = selected_box_com.find_element(By.XPATH, "//option[text()='Comunity Test']").text
        assert ('Person Test' == selected_person)
        assert 'Costa Rica' in self.selenium.page_source
        assert ('Comunity Test' == selected_comunity)
        time.sleep(1)

    def test_arrows_people_group(self):
        url = self.live_server_url + str(reverse('select2box-group-add'))
        time.sleep(4)
        self.selenium.get(url)
        person_available = Select(
            self.selenium.find_element(By.CLASS_NAME, 'select2box_options'))
        test = self.selenium.find_element(By.CLASS_NAME, 'select2box_options')
        person_selected = Select(self.selenium.find_element(By.ID, 'id_people'))
        select_btn = self.selenium.find_element(By.CLASS_NAME, 'add_selection')
        return_btn = self.selenium.find_element(By.CLASS_NAME, 'return_selected')
        person_available.select_by_visible_text('Person Test')
        select_btn.click()
        time.sleep(1)
        person_selected.select_by_visible_text('Person Test')
        return_btn.click()
        time.sleep(1)
        returned_person = test.find_element(By.XPATH,
                                            "//option[text()='Person Test']").text
        assert ('Person Test' == returned_person)
        time.sleep(1)

    def test_people_group_add_new_data(self):
        url = self.live_server_url + str(reverse('select2box-group-add'))
        self.selenium.get(url)
        create_person = self.selenium.find_elements(By.CLASS_NAME, 'create_btn')[1]
        modal = self.selenium.find_elements(By.CLASS_NAME, 'insert_model_data_form')[1]
        modal_f = self.selenium.find_elements(By.CLASS_NAME, 'save_data_btn')[1]

        create_person.click()
        name = modal.find_element(By.ID, 'id_name')
        name.send_keys('New Comunity 2')
        time.sleep(2)
        modal_f.click()
        time.sleep(1)
        assert 'New Comunity 2' in self.selenium.page_source
        time.sleep(1)

    def test_new_people_group(self):
        self.selenium.maximize_window()
        url = self.live_server_url + str(reverse('select2box-group-add'))
        self.selenium.get(url)
        name = self.selenium.find_element(By.ID, 'id_name')
        name.send_keys('Test Group 2')
        time.sleep(2)
        select_boxes = self.selenium.find_elements(By.CLASS_NAME, 'select2box_options')
        add_btns = self.selenium.find_elements(By.CLASS_NAME, 'add_selection')
        person_available = Select(select_boxes[0])
        com_available = Select(select_boxes[1])
        save_btn = self.selenium.find_element(By.CLASS_NAME, 'btn-success')
        person_available.select_by_visible_text('Person Test')
        com_available.select_by_visible_text('Comunity Test')
        add_btns[0].click()
        add_btns[1].click()
        time.sleep(1)
        save_btn.click()
        time.sleep(1)

class Select2BoxPersonFormSeleniumTest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(p):
        super(Select2BoxPersonFormSeleniumTest, p).setUpClass()

        p.timeout = 10
        p.selenium = WebDriver()
        p.selenium.implicitly_wait(p.timeout)

    def setUp(self):

        self.country = Country.objects.create(name='Costa Rica')
        self.items = ChoiceItem.objects.create(name='Item Test')
        self.persons = Person.objects.create(name='Person Test', num_children=4, country= self.country, born_date=date.today(), last_time=timezone.now())
        self.person_group = PersonGroup.objects.create()
        self.person_group.items.add(self.items)
        self.person_group.persons.add(self.persons)

    @classmethod
    def tearDownClass(p):
        p.selenium.quit()
        super(Select2BoxPersonFormSeleniumTest, p).tearDownClass()

    def test_person_group_showing(self):
        url = self.live_server_url + str(reverse('select2box-list'))
        self.selenium.get(url)

        assert f"Group {self.person_group.pk}" in self.selenium.page_source
        time.sleep(1)

    def test_person_group_edit(self):
        url = self.live_server_url + str(reverse('select2box-list'))
        self.selenium.get(url)
        edit_btn = self.selenium.find_element(By.CLASS_NAME, 'btn-outline-warning')
        edit_btn.click()
        time.sleep(2)
        selected_box = self.selenium.find_element(By.ID, 'id_items')
        selected_box_com = self.selenium.find_element(By.ID, 'id_persons')
        selected_persons = selected_box.find_element(By.XPATH, "//option[text()='Person Test']").text
        selected_items = selected_box_com.find_element(By.XPATH, "//option[text()='Item Test']").text
        assert ('Person Test' == selected_persons)
        assert 'Person Test' in self.selenium.page_source
        assert ('Item Test' == selected_items)
        time.sleep(1)

    def test_arrows_person_group(self):
        url = self.live_server_url + str(reverse('select2box-add'))
        time.sleep(2)
        self.selenium.get(url)
        person_available = Select(
            self.selenium.find_element(By.CLASS_NAME, 'select2box_options'))
        test = self.selenium.find_element(By.CLASS_NAME, 'select2box_options')
        person_selected = Select(self.selenium.find_element(By.ID, 'id_persons'))
        select_btn = self.selenium.find_element(By.CLASS_NAME,value='add_selection')
        return_btn = self.selenium.find_element(By.CLASS_NAME,value='return_selected')
        person_available.select_by_visible_text('Person Test')
        select_btn.click()
        time.sleep(2)
        person_selected.select_by_visible_text('Person Test')
        return_btn.click()
        time.sleep(2)
        returned_person = test.find_element(By.XPATH,
                                            "//option[text()='Person Test']").text

        #assert returned_person == "Person Test"
        assert ('Person Test' == returned_person)
        time.sleep(2)
