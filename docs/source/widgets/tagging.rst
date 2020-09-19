Tagging Widget
^^^^^^^^^^^^^^^^^^^

.. image:: ../_static/tagging.png
  

This widget approach used tagify js for make CharField and Textfield taggiable, all data
are saved separated by comma

Example of use:

.. code:: python

    from djgentelella.forms.forms import GTForm
    from djgentelella.widgets.tagging import TaggingInput, EmailTaggingInput
    class TaggingForm(GTForm, forms.ModelForm):
        class Meta:
            model = TaggingModel
            fields = '__all__'
            widgets = {
            'text_list': TaggingInput,
            'email_list':  EmailTaggingInput,
            'area_list': TaggingInput
            }

`EmailTaggingInput` allow only tag emails, so they make a validation on GUI.

.. note:: No email validation are made on server side.