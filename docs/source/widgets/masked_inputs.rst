Masked Input Widgets
^^^^^^^^^^^^^^^^^^^^^^

.. image:: ../_static/InputMask.png

Input mask widgets guide users to enter data in specific formats by displaying a mask pattern and validating input as they type.

-----------------
EmailMaskInput
-----------------

An email input with masking that guides users to enter valid email addresses.

.. code:: python

    from djgentelella.widgets import core as genwidgets
    from djgentelella.forms.forms import GTForm

    class ContactForm(GTForm, forms.Form):
        email = forms.EmailField(widget=genwidgets.EmailMaskInput)

    class UserForm(GTForm, forms.ModelForm):
        class Meta:
            model = User
            fields = ['username', 'email']
            widgets = {
                'username': genwidgets.TextInput,
                'email': genwidgets.EmailMaskInput,
            }

--------------------
PhoneNumberMaskInput
--------------------

A phone number input with formatting mask.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class CustomerForm(GTForm, forms.ModelForm):
        class Meta:
            model = Customer
            fields = ['name', 'phone']
            widgets = {
                'name': genwidgets.TextInput,
                'phone': genwidgets.PhoneNumberMaskInput,
            }

----------------------------
PhoneNumberTwoDigitMaskInput
----------------------------

An alternative phone number format with two-digit area code.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class ContactInfoForm(GTForm, forms.Form):
        phone = forms.CharField(widget=genwidgets.PhoneNumberTwoDigitMaskInput)

-----------------
DateMaskInput
-----------------

A date input with format masking (e.g., DD/MM/YYYY).

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class EventForm(GTForm, forms.Form):
        event_date = forms.DateField(widget=genwidgets.DateMaskInput)

-----------------
DateTimeMaskInput
-----------------

A datetime input with format masking.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class ScheduleForm(GTForm, forms.Form):
        scheduled_time = forms.DateTimeField(widget=genwidgets.DateTimeMaskInput)

---------------------
SerialNumberMaskInput
---------------------

An input formatted for serial numbers.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class ProductForm(GTForm, forms.ModelForm):
        class Meta:
            model = Product
            fields = ['name', 'serial_number']
            widgets = {
                'name': genwidgets.TextInput,
                'serial_number': genwidgets.SerialNumberMaskInput,
            }

-----------------
TaxIDMaskInput
-----------------

An input formatted for tax identification numbers.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class CompanyForm(GTForm, forms.ModelForm):
        class Meta:
            model = Company
            fields = ['name', 'tax_id']
            widgets = {
                'name': genwidgets.TextInput,
                'tax_id': genwidgets.TaxIDMaskInput,
            }

-------------------
CreditCardMaskInput
-------------------

An input formatted for credit card numbers with automatic spacing.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class PaymentForm(GTForm, forms.Form):
        card_number = forms.CharField(
            widget=genwidgets.CreditCardMaskInput,
            label='Credit Card Number'
        )

---------------------------------
Complete Example
---------------------------------

A form demonstrating all masked input widgets:

.. code:: python

    from django import forms
    from djgentelella.widgets import core as genwidgets
    from djgentelella.forms.forms import GTForm

    class InputMaskForm(GTForm, forms.ModelForm):
        class Meta:
            model = InputMaskModel
            fields = '__all__'
            widgets = {
                'phone': genwidgets.PhoneNumberMaskInput,
                'date': genwidgets.DateMaskInput,
                'serial_number': genwidgets.SerialNumberMaskInput,
                'taxid': genwidgets.TaxIDMaskInput,
                'credit_card': genwidgets.CreditCardMaskInput,
                'email': genwidgets.EmailMaskInput,
            }

This form provides guided input for all common masked data types.
