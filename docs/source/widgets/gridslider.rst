GridSlider Widgets, DateGridSlider and SingleGridSlider widgets
^^^^^^^^^^^^^^^^^^^
.. image:: _static/GridSlider.png
.. image:: _static/GridSlider.gif
------------
GridSlider
------------
It is similar to range input, but this use two handle represent the min and max value. 

You need add in the widget a list with especifics atributes.

In the GridSlider need to add:
 - data-min: this atribute receives the min value,in addition can be use with values type integer.
 - data-max: this atribute receives the max value,in addition can be use with values type integer.
 - data-step: this atribute receives the step value requerid to reach the maximum or minimum value.
 - data-grid: this atribute receive true or false value, if the value is true it show a grid under the bar with some step values, but the value is false don't appear the grid.  
 - data-to_max: this atribute defined the default min value and receive integer or date values. 
 - data-from_min:This defined the default max value and receive integer or date values.
 - data-from_fixed: this atribute receive true or false value, it function is limit the minimun value for the slider dont move to more that *data_to_min* atribute.
 - data-to_fixed:this atribute receive true or false value, it function is limit the maximum value for the slider dont move more that *data_to_max* atribute
 - data-prefix: This receive the simbols can use to represent money example: *$* and *€*.
 - data-hide_min_max:this atribute receive true or false value, it function is appear labels with the min a max value.
 - data-target_from: this receive the name of one field of the model and that field represent the minimum value of the grid slider. 
 - data-target_to:this receive the name of one field of the model and that field represent the maximum value of the grid slider.
.. image:: _static/GridSlider_example.gif

Note: You can use this widget only in IntegerField.

----------------
SingleGridSlider
----------------
It is similar to *GridSlider*, but this only  with a handle, you can use the widget to select a number or prices only moving the handle. 
You need add in this widget a list with especifics atributes:
 - data-min: this atribute receives the min value,in addition can be use with values type integer.
 - data-max: this atribute receives the max value,in addition can be use with values type integer.
 - data_from: This defined the default initial value and only date values.
 - data-target: this receive the name of  field and that field represent the minimum value also this is required to edit that value. 

.. image:: _static/SimpleGridSlider.gif

Note: You can use this widget only in IntegerField.
In Meta class:
.. code:: python
from demoapp import models
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import gridslider as widget

class gridSliderForm(forms.ModelForm, GTForm):
 class Meta:
  model = models.gridSlider
  fields = '__all__'
  widgets = {
  age:  widget.SingleGridSlider(attrs={'data-min': '0',
                                       'data-max': '100',
                                       'data_from': '20',
                                       'data-prefix': ' ',
                                       'data-target': 'age',
                                        })
    }
---------------
DateGridSlider
--------------
It is similar to *SingleGridSlider*, but this only receive values type date in format('yyyy/mm/dd' hh:mm:ss), 
but this widget only can used for DateTimeField . 
You need add in this widget a list with especifics atributes:
 - data-min: this atribute receives the min value,in addition can be use with values type date in format ('YYYY / MM / DD').
 - data-max: this atribute receives the max value,in addition can be use with values type date in format ('YYYY / MM / DD').
 - data_from: This defined the default initial value and only date values.
 - data-target: this receive the name of  field and that field represent the minimum value also this is required to edit that value. 

In Meta class:
.. code:: python
from demoapp import models
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import gridslider as widget

class gridSliderForm(forms.ModelForm, GTForm):
 class Meta:
  model = models.gridSlider
  fields = '__all__'
  widgets = {
 
  datetime: widget.DateGridSlider(attrs={'data_min': '2020-09-12 00:00',
                                          'data_max': '2020-12-12 24:00',
                                          'data_from': '2020-11-12 00:00',
                                          'data-target': 'datetime',
                                           }),
    }
.. image:: _static/DateGridSlider.gif

Note: You can use this widget only in DateTimeField.

--------
Forms.py
--------

In model based form:

.. code-block:: python
from django import forms
from demoapp import models
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import gridslider as widget

class gridSliderForm(forms.ModelForm, GTForm):

    grid_slider = forms.CharField(widget=widget.GridSlider(attrs={'data-min': '0',
                                                                  'data-max': '1000',
                                                                  'data-step': 2,
                                                                  'data-grid': 'true',
                                                                  'data-from_fixed': 'false',
                                                                  'data-prefix': "$",
                                                                  'data-to_fixed': 'false',
                                                                  'data-to_max': 800,
                                                                  'data-from_min': 200,
                                                                  'data-hide_min_max': 'true',
                                                                  'data-target-from': 'minimum',
                                                                  'data-target-to': 'maximum',
                                                                  }
                                                           ))


    class Meta:
        model = models.gridSlider
        fields = '__all__'
        widgets = {
            'minimum': widget.HiddenInput,
            'maximum': widget.HiddenInput,
            'datetime': widget.DateGridSlider(attrs={'data_min': '2020-09-12 00:00',
                                                     'data_max': '2020-12-12 24:00',
                                                     'data_from': '2020-11-12 00:00',
                                                     'data-target': 'datetime',
                                                                        }),
            'age':  widget.SingleGridSlider(attrs={'data-min': '0',
                                                   'data-max': '100',
                                                   'data_from': '20',
                                                   'data-prefix': ' ',
                                                   'data-target': 'age',

                                                   })
        }

As you can see in the previous code you can make the fields of the class Meta to be hidden.