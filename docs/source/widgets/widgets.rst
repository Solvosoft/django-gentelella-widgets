Widgets Overview
=================

Django Gentelella Widgets provides a comprehensive set of form widgets that replace Django's default widgets with Bootstrap 5 styled, feature-rich alternatives.

-----------------
Quick Start
-----------------

Import widgets from the core module:

.. code:: python

    from djgentelella.widgets import core as genwidgets

Use them in your forms:

.. code:: python

    from django import forms
    from djgentelella.forms.forms import GTForm
    from djgentelella.widgets import core as genwidgets

    class MyForm(GTForm, forms.Form):
        name = forms.CharField(widget=genwidgets.TextInput)
        email = forms.EmailField(widget=genwidgets.EmailInput)
        birth_date = forms.DateField(widget=genwidgets.DateInput)

Or with ModelForm:

.. code:: python

    class MyModelForm(GTForm, forms.ModelForm):
        class Meta:
            model = MyModel
            fields = ['name', 'email', 'country', 'description']
            widgets = {
                'name': genwidgets.TextInput,
                'email': genwidgets.EmailInput,
                'country': genwidgets.Select,
                'description': genwidgets.Textarea,
            }

-----------------
Widget Categories
-----------------

**Core Inputs** (``djgentelella.widgets.core``)

- ``TextInput`` - Text input field
- ``NumberInput`` - Integer input
- ``FloatInput`` - Decimal input
- ``EmailInput`` - Email field
- ``URLInput`` - URL field
- ``PasswordInput`` - Password field
- ``HiddenInput`` - Hidden field
- ``ColorInput`` - Color picker
- ``Textarea`` - Multi-line text

**Select Widgets** (``djgentelella.widgets.core``)

- ``Select`` - Single select dropdown (Select2)
- ``SelectMultiple`` - Multi-select dropdown
- ``SelectWithAdd`` - Select with add new option
- ``SelectMultipleAdd`` - Multi-select with add new
- ``RadioHorizontalSelect`` / ``RadioVerticalSelect`` - Radio buttons
- ``NullBooleanSelect`` - Yes/No/Unknown
- ``CheckboxInput`` - Single checkbox
- ``CheckboxSelectMultiple`` - Multiple checkboxes

**Date/Time Widgets** (``djgentelella.widgets.core``)

- ``DateInput`` - Date picker
- ``DateTimeInput`` - DateTime picker
- ``TimeInput`` - Time picker
- ``DateRangeInput`` - Date range selector
- ``DateRangeInputCustom`` - Date range with presets
- ``DateRangeTimeInput`` - DateTime range
- ``SplitDateTimeWidget`` - Separate date/time inputs
- ``SelectDateWidget`` - Dropdown date selector

**Masked Inputs** (``djgentelella.widgets.core``)

- ``EmailMaskInput`` - Email with mask
- ``PhoneNumberMaskInput`` - Phone with mask
- ``DateMaskInput`` - Date with mask
- ``CreditCardMaskInput`` - Credit card format
- ``TaxIDMaskInput`` - Tax ID format
- ``SerialNumberMaskInput`` - Serial number format

**File Widgets** (``djgentelella.widgets.core`` and ``djgentelella.widgets.files``)

- ``FileInput`` - File upload with chunking
- ``ClearableFileInput`` - File with clear option
- ``FileChunkedUpload`` - Large file upload
- ``ImageRecordInput`` - Camera capture
- ``VideoRecordInput`` - Video recording
- ``AudioRecordInput`` - Audio recording

**Autocomplete Widgets** (``djgentelella.widgets.selects``)

- ``AutocompleteSelect`` - Single select with remote search
- ``AutocompleteSelectMultiple`` - Multi-select with remote search
- ``AutocompleteSelectImage`` - Image selection
- ``AutocompleteSelectMultipleImage`` - Multiple image selection

**Slider Widgets** (``djgentelella.widgets.core``)

- ``GridSlider`` - Range slider
- ``SingleGridSlider`` - Single value slider
- ``DateGridSlider`` - Date range slider

**Special Widgets**

- ``YesNoInput`` - Toggle with field visibility control
- ``NumberKnobInput`` - Circular knob input (``djgentelella.widgets.numberknob``)
- ``TaggingInput`` / ``EmailTaggingInput`` - Tag inputs (``djgentelella.widgets.tagging``)
- ``EditorTinymce`` - WYSIWYG editor (``djgentelella.widgets.tinymce``)
- ``CalendarInput`` - Calendar widget (``djgentelella.widgets.calendar``)
- ``DigitalSignatureInput`` - Digital signature (``djgentelella.widgets.digital_signature``)

**Visualization Widgets** (readonly display)

- ``UrlTimeLineInput`` - Timeline display (``djgentelella.widgets.timeline``)
- ``UrlStoryLineInput`` - Storyline display (``djgentelella.widgets.storyline``)
- ``MapBasedStoryMapInput`` - Map story (``djgentelella.widgets.storymap``)
- ``GigaPixelStoryMapInput`` - High-res image story (``djgentelella.widgets.storymap``)

**Tree Widgets** (``djgentelella.widgets.trees``)

- ``TreeSelect`` - Hierarchical single select
- ``TreeSelectMultiple`` - Hierarchical multi-select
- ``TreeSelectWithAdd`` - Tree select with add new
- ``TreeSelectMultipleWithAdd`` - Tree multi-select with add new

------------------
Passing Attributes
------------------

All widgets accept an ``attrs`` parameter for HTML attributes:

.. code:: python

    class MyForm(GTForm, forms.Form):
        name = forms.CharField(
            widget=genwidgets.TextInput(attrs={
                'placeholder': 'Enter your name',
                'class': 'custom-class',
                'data-custom': 'value',
                'maxlength': 100,
            })
        )

Common attributes:

- ``placeholder`` - Placeholder text
- ``class`` - Additional CSS classes
- ``data-*`` - Custom data attributes for JavaScript
- ``disabled`` - Disable the input
- ``readonly`` - Make read-only

-----------------
API Reference
-----------------

Core Widgets
^^^^^^^^^^^^^^^^^^^^^

.. automodule:: djgentelella.widgets.core
   :members:

Tree Widgets
^^^^^^^^^^^^^^^^^^^

Django Gentelella uses django-tree-queries for tree database representations.

.. automodule:: djgentelella.widgets.trees
   :members:

TinyMCE Widget
^^^^^^^^^^^^^^^^^^^

.. automodule:: djgentelella.widgets.tinymce
   :members:
