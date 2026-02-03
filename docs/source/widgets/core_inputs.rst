Core Input Widgets
^^^^^^^^^^^^^^^^^^^

These are the fundamental input widgets that replace Django's default form inputs with Bootstrap 5 styled versions.

-----------------
TextInput
-----------------

A styled text input field with Bootstrap form-control class.

.. code:: python

    from djgentelella.widgets import core as genwidgets
    from djgentelella.forms.forms import GTForm

    class MyForm(GTForm, forms.ModelForm):
        class Meta:
            model = MyModel
            fields = ['name', 'title']
            widgets = {
                'name': genwidgets.TextInput,
                'title': genwidgets.TextInput(attrs={
                    'placeholder': 'Enter title here',
                    'maxlength': 100
                }),
            }

You can pass any HTML attributes via the ``attrs`` parameter.

-----------------
NumberInput
-----------------

A numeric input with HTML5 validation for integer values.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class ProductForm(GTForm, forms.ModelForm):
        class Meta:
            model = Product
            fields = ['quantity', 'price']
            widgets = {
                'quantity': genwidgets.NumberInput,
                'price': genwidgets.NumberInput(attrs={
                    'min': 0,
                    'max': 10000,
                    'step': 1
                }),
            }

-----------------
FloatInput
-----------------

A numeric input configured for decimal values with step of 0.1 by default.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class MeasurementForm(GTForm, forms.ModelForm):
        class Meta:
            model = Measurement
            fields = ['weight', 'temperature']
            widgets = {
                'weight': genwidgets.FloatInput,
                'temperature': genwidgets.FloatInput(attrs={
                    'step': '0.01',
                    'min': '-273.15'
                }),
            }

-----------------
EmailInput
-----------------

An email input with HTML5 email validation.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class ContactForm(GTForm, forms.Form):
        email = forms.EmailField(widget=genwidgets.EmailInput)
        secondary_email = forms.EmailField(
            widget=genwidgets.EmailInput(attrs={
                'placeholder': 'backup@example.com'
            }),
            required=False
        )

-----------------
URLInput
-----------------

A URL input with ``https://`` placeholder by default.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class WebsiteForm(GTForm, forms.ModelForm):
        class Meta:
            model = Website
            fields = ['homepage', 'social_link']
            widgets = {
                'homepage': genwidgets.URLInput,
                'social_link': genwidgets.URLInput(attrs={
                    'placeholder': 'https://twitter.com/username'
                }),
            }

-----------------
PasswordInput
-----------------

A password input that masks the entered text.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class RegistrationForm(GTForm, forms.Form):
        password = forms.CharField(widget=genwidgets.PasswordInput)
        confirm_password = forms.CharField(
            widget=genwidgets.PasswordInput(attrs={
                'autocomplete': 'new-password'
            })
        )

-----------------
HiddenInput
-----------------

A hidden input field for storing values not visible to the user.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class OrderForm(GTForm, forms.ModelForm):
        class Meta:
            model = Order
            fields = ['product', 'user_id']
            widgets = {
                'user_id': genwidgets.HiddenInput,
            }

-----------------
ColorInput
-----------------

An HTML5 color picker widget.

.. image:: ../_static/color.gif

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class ThemeForm(GTForm, forms.ModelForm):
        class Meta:
            model = Theme
            fields = ['primary_color', 'secondary_color']
            widgets = {
                'primary_color': genwidgets.ColorInput,
                'secondary_color': genwidgets.ColorInput(attrs={
                    'value': '#3498db'
                }),
            }

-----------------
Textarea
-----------------

A resizable text area with Bootstrap styling.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class ArticleForm(GTForm, forms.ModelForm):
        class Meta:
            model = Article
            fields = ['title', 'content', 'summary']
            widgets = {
                'title': genwidgets.TextInput,
                'content': genwidgets.Textarea,
                'summary': genwidgets.Textarea(attrs={
                    'rows': 5,
                    'placeholder': 'Brief summary of the article...'
                }),
            }

By default, the textarea has 3 rows and is resizable.
