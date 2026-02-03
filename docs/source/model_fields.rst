Model Fields
==============

Django Gentelella Widgets provides custom model fields, form fields, and serializer fields for specialized use cases.

Secure Fields (Encryption)
----------------------------

These fields provide AES encryption for sensitive data stored in the database.

GTEncryptedText
"""""""""""""""""

A TextField that automatically encrypts data before saving and decrypts when loading.

.. code:: python

    from django.db import models
    from djgentelella.fields.secure import GTEncryptedText

    class UserProfile(models.Model):
        user = models.OneToOneField(User, on_delete=models.CASCADE)
        social_security_number = GTEncryptedText(null=True, blank=True)
        private_notes = GTEncryptedText()

**Features:**

- Uses AES encryption with EAX mode
- Derives encryption key from Django's ``SECRET_KEY``
- Transparent encryption/decryption on save/load
- Stores nonce and authentication tag with encrypted data

.. warning::
    Changing your ``SECRET_KEY`` will make previously encrypted data unreadable.

GTEncryptedJSONField
""""""""""""""""""""""

A JSONField that encrypts the entire JSON payload before storage.

.. code:: python

    from django.db import models
    from djgentelella.fields.secure import GTEncryptedJSONField

    class SecureConfig(models.Model):
        name = models.CharField(max_length=100)
        api_credentials = GTEncryptedJSONField(null=True, blank=True)

**Usage:**

.. code:: python

    config = SecureConfig.objects.create(
        name="Payment Gateway",
        api_credentials={
            "api_key": "sk_live_xxxxx",
            "api_secret": "whsec_xxxxx",
            "merchant_id": "12345"
        }
    )

    # Data is encrypted in database but accessible as dict
    print(config.api_credentials['api_key'])  # "sk_live_xxxxx"


Catalog Fields (Filtered Relationships)
-----------------------------------------

These fields extend Django's relationship fields with built-in queryset filtering.

GTForeignKey
""""""""""""""

A ForeignKey with automatic queryset filtering based on specified criteria.

.. code:: python

    from django.db import models
    from djgentelella.fields.catalog import GTForeignKey

    class Category(models.Model):
        name = models.CharField(max_length=100)
        category_type = models.CharField(max_length=50)
        is_active = models.BooleanField(default=True)

    class Product(models.Model):
        name = models.CharField(max_length=200)

        # Only show categories where category_type='product' and is_active=True
        category = GTForeignKey(
            Category,
            on_delete=models.CASCADE,
            key_name='category_type',
            key_value='product',
            extra_filters={'is_active': True}
        )

**Parameters:**

- ``key_name`` - Field name to filter by
- ``key_value`` - Value to match for the filter
- ``extra_filters`` - Dictionary of additional filter conditions

GTOneToOneField
"""""""""""""""""

OneToOne relationship with the same filtering capabilities as GTForeignKey.

.. code:: python

    from djgentelella.fields.catalog import GTOneToOneField

    class UserSettings(models.Model):
        user = models.OneToOneField(User, on_delete=models.CASCADE)

        # Link to a specific config type
        config = GTOneToOneField(
            Configuration,
            on_delete=models.SET_NULL,
            null=True,
            key_name='config_type',
            key_value='user_settings'
        )

GTManyToManyField
"""""""""""""""""""

ManyToMany relationship with queryset filtering.

.. code:: python

    from djgentelella.fields.catalog import GTManyToManyField

    class Article(models.Model):
        title = models.CharField(max_length=200)

        # Only show active tags in forms
        tags = GTManyToManyField(
            Tag,
            key_name='is_active',
            key_value=True,
            blank=True
        )


Tree Fields (MPTT Support)
----------------------------

Form fields for working with tree-structured data using MPTT.

GentelellaTreeNodeChoiceField
"""""""""""""""""""""""""""""""

A select field for choosing a single node from a tree structure.

.. code:: python

    from django import forms
    from djgentelella.fields.tree import GentelellaTreeNodeChoiceField
    from myapp.models import Category  # MPTT model

    class ProductForm(forms.Form):
        category = GentelellaTreeNodeChoiceField(
            queryset=Category.objects.all(),
            disable0=True,  # Disable root level (level 0)
            disable1=False,  # Enable level 1
            disable2=False,  # Enable level 2
        )

**Parameters:**

- ``disable0``, ``disable1``, ``disable2``, etc. - Disable selection for specific tree levels

GentelellaTreeNodeMultipleChoiceField
"""""""""""""""""""""""""""""""""""""""

Multi-select version for choosing multiple tree nodes.

.. code:: python

    from djgentelella.fields.tree import GentelellaTreeNodeMultipleChoiceField

    class ArticleForm(forms.Form):
        categories = GentelellaTreeNodeMultipleChoiceField(
            queryset=Category.objects.all(),
            disable0=True,  # Can't select root categories
        )


DRF Serializer Fields
-----------------------

Custom Django REST Framework fields for file handling.

GTBase64FileField
"""""""""""""""""""

Handles file uploads from base64-encoded data in API requests.

.. code:: python

    from rest_framework import serializers
    from djgentelella.fields.files import GTBase64FileField

    class DocumentSerializer(serializers.ModelSerializer):
        file = GTBase64FileField(max_files=5, delete_if_empty=False)

        class Meta:
            model = Document
            fields = ['id', 'name', 'file']

**Request format:**

.. code:: json

    {
        "name": "My Document",
        "file": [
            {
                "name": "document.pdf",
                "value": "JVBERi0xLjQKJe..."
            }
        ]
    }

**Parameters:**

- ``max_files`` - Maximum number of files allowed (default: 1)
- ``delete_if_empty`` - Delete existing file if empty submission (default: True)

ChunkedFileField
""""""""""""""""""

Handles resumable/chunked file uploads for large files.

.. code:: python

    from rest_framework import serializers
    from djgentelella.fields.files import ChunkedFileField

    class LargeFileSerializer(serializers.ModelSerializer):
        file = ChunkedFileField()

        class Meta:
            model = LargeFile
            fields = ['id', 'name', 'file']

**Features:**

- Integrates with ``djgentelella.chunked_upload`` module
- Supports resumable uploads
- Handles upload tokens and metadata

DigitalSignatureField
"""""""""""""""""""""""

Handles digital signature file uploads with Firmador Libre integration.

.. code:: python

    from rest_framework import serializers
    from djgentelella.fields.files import DigitalSignatureField

    class SignedDocumentSerializer(serializers.ModelSerializer):
        signature_file = DigitalSignatureField()

        class Meta:
            model = SignedDocument
            fields = ['id', 'document', 'signature_file']


Date/Time Serializer Fields
-----------------------------

Custom DRF fields that handle empty strings gracefully.

GTDateField
"""""""""""""

DateField that accepts empty strings without validation errors.

.. code:: python

    from rest_framework import serializers
    from djgentelella.serializers import GTDateField

    class PersonSerializer(serializers.ModelSerializer):
        birth_date = GTDateField(allow_empty_str=True)

        class Meta:
            model = Person
            fields = ['name', 'birth_date']

GTDateTimeField
"""""""""""""""""

DateTimeField that accepts empty strings without validation errors.

.. code:: python

    from djgentelella.serializers import GTDateTimeField

    class EventSerializer(serializers.ModelSerializer):
        start_time = GTDateTimeField(allow_empty_str=True)
        end_time = GTDateTimeField(allow_empty_str=True)

        class Meta:
            model = Event
            fields = ['title', 'start_time', 'end_time']

.. note::
    These fields are especially useful with DataTables where empty filter values are sent as empty strings.


Date Range Form Widgets
-------------------------

Widgets for selecting date ranges in forms.

DateRangeTextWidget
"""""""""""""""""""""

Text input that parses date range in "start - end" format.

.. code:: python

    from django import forms
    from django_filters import FilterSet, DateFromToRangeFilter
    from djgentelella.fields.drfdatetime import DateRangeTextWidget

    class EventFilterSet(FilterSet):
        date_range = DateFromToRangeFilter(
            widget=DateRangeTextWidget(attrs={'placeholder': 'YYYY-MM-DD'})
        )

        class Meta:
            model = Event
            fields = ['date_range']

DateTimeRangeTextWidget
"""""""""""""""""""""""""

Similar widget for datetime ranges including time component.

.. code:: python

    from djgentelella.fields.drfdatetime import DateTimeRangeTextWidget

    class LogFilterSet(FilterSet):
        timestamp_range = DateTimeFromToRangeFilter(
            widget=DateTimeRangeTextWidget(
                attrs={'placeholder': 'YYYY-MM-DD HH:MM:SS'}
            )
        )


API Reference
---------------

Secure Fields
""""""""""""""

.. automodule:: djgentelella.fields.secure
   :members:

Catalog Fields
""""""""""""""""

.. automodule:: djgentelella.fields.catalog
   :members:

Tree Fields
"""""""""""""

.. automodule:: djgentelella.fields.tree
   :members:

File Fields
"""""""""""""

.. automodule:: djgentelella.fields.files
   :members:

