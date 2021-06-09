ChunkedUpload widget
^^^^^^^^^^^^^^^^^^^^

.. image:: ../_static/chunkedupload.png

This widget approach used django-chunked-upload app for save the files to the respective directory.
You can add this widget only in a *FileField*.

The widget can be use in the Meta or in a field of the form.

In Meta class:

.. code:: python

    from djgentelella.widgets.core import TextInput
    from djgentelella.widgets.files import FileChunkedUpload
    from djgentelella.forms.forms import GTForm

    class ChunkedUploadItemForm(GTForm, forms.ModelForm):
        fileexample = forms.FileField(widget=FileChunkedUpload, required=False)
        class Meta:
            model = ChunkedUploadItem
            fields = '__all__'
            widgets = {
                'name': TextInput,
                'fileexample': FileChunkedUpload
            }

As a Form field:

.. code:: python

    from djgentelella.widgets.core import TextInput
    from djgentelella.widgets.files import FileChunkedUpload
    from djgentelella.forms.forms import GTForm

    class ChunkedUploadItemForm(GTForm, forms.ModelForm):
        fileexample = forms.FileField(widget=FileChunkedUpload, required=False)
        class Meta:
            model = ChunkedUploadItem
            fields = '__all__'

Make sure your model has the `fileexample` or the name of the field do you using to save file in your model.

.. note:: If you send a null value using this widget, do you has to validate when need to see the value for example:

