======================
NumberKnobInput widget
======================

.. image:: _static/knob.png
   :align: center

It is a kind of selector to input numerical values.
You can add this widget in a *IntegerField* or *FloatField.*

.. code:: python

   class FooModelForm(CustomForm, forms.ModelForm):
       class Meta:
           model = Foo
           fields = (
               'number_of_eyes',
               'speed_in_miles_per_hour',
               'age'
           )

       widgets = {
            'number_of_eyes': knobwidget.NumberKnobInput(attrs={}),
            'speed_in_miles_per_hour': knobwidget.NumberKnobInput(
                                            attrs={
                                                "data-min": 1,
                                                "data-step": 0.1,
                                                "data-max": 50
                                            }),
            'age': knobwidget.NumberKnobInput()
       }

As you can see in the previous code you can add min, max and step increment values.