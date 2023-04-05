import time

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium.webdriver import ActionChains
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.webdriver.support.ui import Select
from django.urls import reverse
from demoapp.models import Person, Comunity, PeopleGroup, Country
from selenium.webdriver.common.by import By
from datetime import date

class Select2BoxFormSeleniumTest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super(Select2BoxFormSeleniumTest, cls).setUpClass()

        cls.timeout = 10
        cls.selenium = WebDriver()
        cls.selenium.implicitly_wait(cls.timeout)

    def setUp(self):
        Person.objects.all().delete()
        Comunity.objects.all().delete()
        PeopleGroup.objects.all().delete()
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

    """def test_people_group_showing(self):
        url = self.live_server_url + str(reverse('select2box-group-list'))
        self.selenium.get(url)
        assert 'Group Test' in self.selenium.page_source

    def test_people_group_edit(self):
        url = self.live_server_url + str(reverse('select2box-group-list'))
        self.selenium.get(url)
        edit_btn = self.selenium.find_element(By.CLASS_NAME, 'btn-outline-warning')
        edit_btn.click()
        time.sleep(5)
        selected_box = self.selenium.find_element(By.ID, 'id_people')
        selected_box_com = self.selenium.find_element(By.ID, 'id_comunities')
        selected_person = selected_box.find_element(By.XPATH, "//option[text()='Person Test']").text
        selected_comunity = selected_box_com.find_element(By.XPATH, "//option[text()='Comunity Test']").text
        assert ('Person Test' == selected_person)
        assert 'Costa Rica' in self.selenium.page_source
        assert ('Comunity Test' == selected_comunity)



    def test_return_arrow_people_group(self):
        url = self.live_server_url + str(reverse('select2box-group-list'))
        self.selenium.get(url)
        edit_btn = self.selenium.find_element(By.CLASS_NAME, 'btn-outline-warning')
        edit_btn.click()
        time.sleep(3)
        return_btn = self.selenium.find_element(By.CLASS_NAME, 'return_selected')
        person_selected = Select(self.selenium.find_element(By.ID, 'id_people'))
        person_selected.select_by_visible_text('Person Test')
        return_btn.click()
        time.sleep(1)
        person_available = self.selenium.find_element(By.CLASS_NAME, 'select2box_options')
        returned_person = person_available.find_element(By.XPATH, "//option[text()='Person Test']").text
        assert ('Person Test' == returned_person)

    def test_add_arrow_people_group(self):
        url = self.live_server_url + str(reverse('select2box-group-add'))
        self.selenium.get(url)
        person_available = Select(self.selenium.find_element(By.CLASS_NAME, 'select2box_options'))
        select_btn = self.selenium.find_element(By.CLASS_NAME, 'add_selection')
        person_available.select_by_visible_text('Person Test')
        select_btn.click()
        time.sleep(1)
        person_selected = self.selenium.find_element(By.ID, 'id_people')
        selected_person = person_selected.find_element(By.XPATH, "//option[text()='Person Test']").text
        assert ('Person Test' == selected_person)"""

    def test_submit_new_people_group(self):
        url = self.live_server_url + str(reverse('select2box-group-add'))
        self.selenium.get(url)
        act = ActionChains(self.selenium)
        name = self.selenium.find_element(By.ID, 'id_name')
        name.send_keys('Test Group 2')
        time.sleep(2)
        select_boxes = self.selenium.find_elements(By.CLASS_NAME, 'select2box_options')
        add_btns = self.selenium.find_elements(By.CLASS_NAME, 'add_selection')
        person_available = Select(select_boxes[0])
        com_available = Select(select_boxes[1])
        save_btn = self.selenium.find_element(By.CLASS_NAME, 'btn-success')
        #comunity_available = Select(self.selenium.find_element(By.ID, 'id_people'))
        person_available.select_by_visible_text('Person Test')
        com_available.select_by_visible_text('Comunity Test')
        add_btns[0].click()
        add_btns[1].click()
        act.move_to_element(save_btn).perform()
        save_btn.click()
        time.sleep(1)

    """def test_people_group_add_new_person(self):
        url = self.live_server_url + str(reverse('select2box-group-add'))
        self.selenium.get(url)
        create_person = self.selenium.find_element(By.CLASS_NAME, 'create_btn')
        create_person.click()

        name = self.selenium.find_element(By.ID, 'id_person_new_data-name')
        num_children = self.selenium.find_element(By.ID, 'id_person_new_data-num_children')
        #country = self.selenium.find_element(By.CLASS_NAME, 'select2-results__options')
        born_dt = self.selenium.find_element(By.ID, 'id_person_new_data-born_date')
        last_t = self.selenium.find_element(By.ID, 'id_person_new_data-last_time')
        born_dt.click()
        last_t.click()
        #country.click()
        name.send_keys('Person Test 2')
        time.sleep(5)"""

