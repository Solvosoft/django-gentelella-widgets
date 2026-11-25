"""W31 in the browser: ``CheckboxSelectMultiple`` drawn as one box per choice
in every layout, and a facets panel that filters cards over an exposed model
(no data source) with their ``site_field``.

The checkbox page is served by this module's own ``urlpatterns``
(``ROOT_URLCONF`` points here), so the demo gets no page just for the test."""
from django import forms
from django.contrib.sites.models import Site
from django.http import HttpResponse
from django.template import Context, Template
from django.test import override_settings, tag
from django.urls import include, path

from demo.urls import urlpatterns as demo_urlpatterns
from demoapp.models import Department
from djgentelella.designs import engine, factories, publishing
from djgentelella.designs.exposure import expose, unexpose
from djgentelella.forms.forms import GTForm
from djgentelella.tests.Designs_Test import design, node
from djgentelella.widgets import core as genwidgets

from .base import By, SeleniumTestCase, WebDriverException

URLCONF = 'demoapp.tests.selenium.test_w31_proposals'
LAYOUTS = ('as_plain', 'as_horizontal', 'as_inline')

PAGE = Template("""
{% extends 'gentelella/base.html' %}
{% block content %}
<form method="post" id="the-form">{{ rendered }}</form>
<p id="after-the-form">After the form</p>
{% endblock %}
""")


class ColorsForm(GTForm, forms.Form):
    colors = forms.MultipleChoiceField(
        choices=[('red', 'Red'), ('green', 'Green'), ('blue', 'Blue'),
                 ('black', 'Black')],
        required=False, widget=genwidgets.CheckboxSelectMultiple)


def colors_view(request, layout):
    if layout not in LAYOUTS:
        return HttpResponse(status=404)
    form = ColorsForm(render_type=layout, initial={'colors': ['green']})
    return HttpResponse(PAGE.render(Context({
        'rendered': getattr(form, layout)(), 'request': request,
        'user': request.user})))


urlpatterns = [
    path('w31-colors/<str:layout>/', colors_view),
    path('', include(demo_urlpatterns)),
]


@tag('selenium')
@override_settings(ROOT_URLCONF=URLCONF)
class CheckboxSelectMultipleTest(SeleniumTestCase):

    def geometry(self):
        return self.js("""
            var list = document.querySelector('#the-form ul.gt-check-list');
            var boxes = Array.prototype.map.call(
                list.querySelectorAll('input[type=checkbox]'), function (box) {
                    var r = box.getBoundingClientRect();
                    return {top: r.top, bottom: r.bottom, left: r.left,
                            width: r.width, height: r.height,
                            checked: box.checked,
                            appearance: getComputedStyle(box).appearance};
                });
            var l = list.getBoundingClientRect();
            return {list: {top: l.top, bottom: l.bottom, height: l.height,
                           width: l.width,
                           border: getComputedStyle(list).borderTopStyle,
                           className: list.className,
                           style: getComputedStyle(list).listStyleType},
                    boxes: boxes,
                    after: document.querySelector('#after-the-form')
                        .getBoundingClientRect().top};
        """)

    def test_one_box_per_choice_in_every_layout(self):
        for layout in LAYOUTS:
            with self.subTest(layout=layout):
                self.go('/w31-colors/%s/' % layout)
                found = self.geometry()
                boxes = found['boxes']
                self.assertEqual(len(boxes), 4)
                # The list is a list, not one more box: no gt-check, no
                # border, wider than a box.
                self.assertEqual(found['list']['className'], 'gt-check-list')
                self.assertEqual(found['list']['border'], 'none')
                self.assertEqual(found['list']['style'], 'none')
                self.assertGreater(found['list']['width'], 3 * boxes[0]['width'])
                for box in boxes:
                    self.assertEqual(box['appearance'], 'none')
                    self.assertGreaterEqual(box['width'], 16)
                    self.assertGreaterEqual(box['height'], 16)
                # One under the other, all inside the list, nothing over what
                # comes after the form.
                tops = [box['top'] for box in boxes]
                self.assertEqual(tops, sorted(tops))
                self.assertEqual(len(set(round(top) for top in tops)), 4)
                self.assertGreaterEqual(found['list']['height'],
                                        sum(box['height'] for box in boxes))
                self.assertLessEqual(boxes[-1]['bottom'], found['list']['bottom'] + 1)
                self.assertGreaterEqual(found['after'], found['list']['bottom'])
                self.assertEqual([box['checked'] for box in boxes],
                                 [False, True, False, False])

    def test_a_box_is_clicked(self):
        self.go('/w31-colors/as_horizontal/')
        box = self.driver.find_element(By.CSS_SELECTOR,
                                       '#the-form input[value="blue"]')
        self.mouse_click(box)
        self.wait_js("return document.querySelector("
                     "  '#the-form input[value=\"blue\"]').checked",
                     message='the box was not checked')
        # Its label too.
        label = self.driver.find_element(
            By.XPATH, '//form[@id="the-form"]//label[normalize-space(.)="Red"]')
        self.mouse_click(label)
        self.wait_js("return document.querySelector("
                     "  '#the-form input[value=\"red\"]').checked",
                     message='the label did not check its box')


@tag('selenium')
class FacetsOverModelCardsTest(SeleniumTestCase):

    def setup_data(self):
        engine.clear_cache()
        factories.clear_cache()
        expose(Department)
        self.addCleanup(unexpose, Department)
        other = Site.objects.create(domain='other.example', name='Other')
        Department.objects.create(name='Sales', head='Eva')
        Department.objects.create(name='Support', head='Leo')
        Department.objects.create(name='Research', head='Eva')
        # Another Site's row: neither a card nor counted.
        Department.objects.create(name='Elsewhere', head='Leo', site=other)
        document = design(
            node('facets', 'filters', {'target': 'units', 'columns': ['head']}),
            node('cards', 'units', {'model': 'demoapp.Department',
                                    'site_field': 'site', 'title_field': 'name',
                                    'fields': ['head']}))
        _page, errors = publishing.publish(document, path='w31-units')
        self.assertEqual(errors, [])

    def titles(self):
        return sorted(self.js(
            "return Array.prototype.map.call(document.querySelectorAll("
            "  '[data-gtdesign=\"units\"] .gtcard .card-title'),"
            "  function (e) { return e.textContent.trim(); });"))

    def click_facet(self, text):
        xpath = ('//div[contains(@class, "gtdesign-facets")]//div[@data-column='
                 '"head"]//label[starts-with(normalize-space(.), "%s")]' % text)

        def click(driver):
            try:
                self.mouse_click(driver.find_element(By.XPATH, xpath))
            except WebDriverException:  # stale or not drawn yet
                return False
            return True

        self.wait.until(click, 'the facet %s could not be clicked' % text)

    def test_the_cards_follow_the_facets(self):
        self.go('/designs/w31-units/')
        self.wait.until(lambda d: self.titles() == ['Research', 'Sales', 'Support'],
                        'the cards never loaded')
        self.wait_js("return document.querySelectorAll("
                     "  '.gtdesign-facets .gt-facet').length === 1",
                     message='the facets never rendered')
        labels = self.js("return Array.prototype.map.call(document.querySelectorAll("
                         "  '.gtdesign-facets label'),"
                         "  function (e) { return e.textContent.trim(); });")
        self.assertEqual(sorted(labels), ['Eva (2)', 'Leo (1)'])
        self.click_facet('Leo')
        self.wait.until(lambda d: self.titles() == ['Support'],
                        'the cards did not follow the facet')
        self.click_facet('Leo')
        self.wait.until(lambda d: len(self.titles()) == 3,
                        'the cards did not come back to every row')
