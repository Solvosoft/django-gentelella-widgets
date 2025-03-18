Django Rest Framework utilities
==================================

This utilities help you with serializers to parse correct the data input.

GTBase64FileField
-------------------

Allow upload files as base64 files, following the format `{name: 'name of file', value:'base64 string representation'}`.

- By default `allow_empty_file` is set True, and allow that user submit empty field, because `<input type="file">` do not allow set upload document, this attribute helps to not update database field if value is empty. So if value is empty and `allow_empty_file` is false then required exception is raise.
- By default `delete_if_empty` is false to prevent deletions when file field is empty, set true if you want to delete the file if value is not set.

.. code:: python

      class MySerializer(serializers.Serializer):
         simple_archive = GTBase64FileField(allow_empty_file=False)

ChunkedFileField
----------------------
Manage uploaded token from ChunkedFileUpload widget and find on server de chunked file.
Internally use this structure:


.. code:: javascript

    // For upload token
    {'name': 'file name', 'token': 'xxxx'}
    // For edit field
    {'name': 'file name', 'display_text': 'file display text', 'url': 'https://...'}
    // for delete field
    {'name': 'file name', 'display_text': 'file display text', 'url': 'https://...', 'actions': 'delete'}


Usage for upload and edit files:

.. code:: python

      class MySerializer(serializers.Serializer):
           chunked_archive = ChunkedFileField()


GTS2SerializerBase
---------------------

This class was designed for other classes to inherit from it and override its attributes. It serves to return an object serialized in the format that select2 understands. Although it can be used directly. The attributes are:


- `id_field`: default 'pk', field to lookup on the model for primary key
- `display_fields`: default '__str__', must be string or list of strings of fields name on model, in case of list will be joined on one string
- `default_selected`: default 'True', mark returned data object as selected, normally only selected data is displayed.
- `default_disable`: default False, mark returned data object as disable, so select2 disabled selections or deselection on gui.

.. code:: python

    class MySerializer(serializer.ModelSerializer):
        m2m_autocomplete = GTS2SerializerBase(many=True)
        ...

GTDateField
-----------------

Same as `DateField` from Django rest Framework, but configure default date input automatically, and allow parsing some
string date representations.


GTDateTimeField
-----------------

Same as `DateTimeField` from Django rest Framework, but configure default datetime input automatically, and allow parsing some
string date representations.




