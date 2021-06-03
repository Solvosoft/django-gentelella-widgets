from .test_base import WidgetTest
from djgentelella.widgets import core as widgets
from datetime import datetime,date

class DateRangeTest(WidgetTest):
    widget=widgets.DateRangeInput()
    
    def test_type(self):
        self.check_type(self.widget,'text')
        
    def test_template_name(self):
        self.check_template_name(self.widget,'gentelella/widgets/daterange.html')
    
    def test_element(self):
        self.assertIn('class', self.widget.render('name', None, attrs={}, renderer=self.django_renderer)
      )
    def test_attrs(self):
        self.assertHTMLEqual(self.widget.render('date', "%s - %s")% (date(2020, 11, 2), date(2020, 12, 2)),
            '<input class="form-control" data-widget="DateRangeInput" name="date" type="text" value="2020-11-02 - 2020-12-02">',
    )

class DateRangeCustomTest(WidgetTest):
    widget=widgets.DateRangeInputCustom()
    
    def test_type(self):
        self.check_type(self.widget,'text')
        
    def test_template_name(self):
        self.check_template_name(self.widget,'gentelella/widgets/daterange.html')
    
    def test_element(self):
        self.assertIn('class', self.widget.render('name', None, attrs={}, renderer=self.django_renderer)
      )
    def test_attrs(self):
        self.assertHTMLEqual(self.widget.render('date', "%s - %s")% (date(2020, 11, 2), date(2020, 12, 2)),
            '<input class="form-control" data-widget="DateRangeInputCustom" name="date" type="text" value="2020-11-02 - 2020-12-02">',
    )

class DateRangeTimeTest(WidgetTest):
    widget=widgets.DateRangeTimeInput()
    
    def test_type(self):
        self.check_type(self.widget,'text')
        
    def test_template_name(self):
        self.check_template_name(self.widget,'gentelella/widgets/daterangetime.html')
    
    def test_element(self):
        self.assertIn('class', self.widget.render('name', None, attrs={}, renderer=self.django_renderer)
      )
    def test_attrs(self):
        self.assertHTMLEqual(self.widget.render('date', "%s - %s")% (datetime(2020, 11, 2,12,10), datetime(2020, 12, 2,12,10)),
            '<input class="form-control" data-widget="DateRangeTimeInput" name="date" type="text" value="2020-11-02 12:10:00 - 2020-12-02 12:10:00">',
    )
