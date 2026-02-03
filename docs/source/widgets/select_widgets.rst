Select Widgets
^^^^^^^^^^^^^^^^^^^

Select widgets provide enhanced dropdown and selection functionality using Select2 and Bootstrap styling.

-----------------
Select
-----------------

A Select2-powered dropdown with autocomplete search.

.. code:: python

    from djgentelella.widgets import core as genwidgets
    from djgentelella.forms.forms import GTForm

    class PersonForm(GTForm, forms.ModelForm):
        class Meta:
            model = Person
            fields = ['country', 'status']
            widgets = {
                'country': genwidgets.Select,
                'status': genwidgets.Select(attrs={
                    'data-placeholder': 'Select a status...'
                }),
            }

For static choices:

.. code:: python

    class SettingsForm(GTForm, forms.Form):
        priority = forms.ChoiceField(
            choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
            widget=genwidgets.Select
        )

-----------------
SelectMultiple
-----------------

A multi-select dropdown allowing multiple selections.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class ProjectForm(GTForm, forms.ModelForm):
        class Meta:
            model = Project
            fields = ['name', 'tags', 'members']
            widgets = {
                'name': genwidgets.TextInput,
                'tags': genwidgets.SelectMultiple,
                'members': genwidgets.SelectMultiple(attrs={
                    'data-placeholder': 'Select team members...'
                }),
            }

-----------------
SelectWithAdd
-----------------

A select dropdown with an "Add New" button to create new options inline.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class DocumentForm(GTForm, forms.ModelForm):
        class Meta:
            model = Document
            fields = ['title', 'category']
            widgets = {
                'title': genwidgets.TextInput,
                'category': genwidgets.SelectWithAdd(attrs={
                    'add_url': '/categories/create/'  # URL to create new category
                }),
            }

.. note:: The ``add_url`` attribute is required and should point to a view that handles creating new options.

-----------------
SelectMultipleAdd
-----------------

A multi-select with "Add New" functionality.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class ArticleForm(GTForm, forms.ModelForm):
        class Meta:
            model = Article
            fields = ['title', 'tags']
            widgets = {
                'title': genwidgets.TextInput,
                'tags': genwidgets.SelectMultipleAdd(attrs={
                    'add_url': '/tags/create/'
                }),
            }

---------------------
RadioHorizontalSelect
---------------------

Displays choices as horizontal radio buttons.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class SurveyForm(GTForm, forms.Form):
        rating = forms.ChoiceField(
            choices=[('1', 'Poor'), ('2', 'Fair'), ('3', 'Good'),
                     ('4', 'Very Good'), ('5', 'Excellent')],
            widget=genwidgets.RadioHorizontalSelect
        )

        gender = forms.ChoiceField(
            choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')],
            widget=genwidgets.RadioHorizontalSelect
        )

-------------------
RadioVerticalSelect
-------------------

Displays choices as vertical radio buttons (one per line).

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class PreferencesForm(GTForm, forms.Form):
        notification_frequency = forms.ChoiceField(
            choices=[
                ('immediate', 'Immediately'),
                ('daily', 'Daily digest'),
                ('weekly', 'Weekly summary'),
                ('never', 'Never')
            ],
            widget=genwidgets.RadioVerticalSelect
        )

You can also use the alias ``RadioSelect`` which defaults to horizontal layout:

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class OptionsForm(GTForm, forms.Form):
        choice = forms.ChoiceField(
            choices=[('a', 'Option A'), ('b', 'Option B')],
            widget=genwidgets.RadioSelect  # Same as RadioHorizontalSelect
        )

-----------------
NullBooleanSelect
-----------------

A three-state selection for nullable boolean fields (Unknown, Yes, No).

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class ReviewForm(GTForm, forms.ModelForm):
        class Meta:
            model = Review
            fields = ['approved', 'featured']
            widgets = {
                'approved': genwidgets.NullBooleanSelect,
                'featured': genwidgets.NullBooleanSelect,
            }

Custom labels can be provided:

.. code:: python

    class CustomNullBooleanForm(GTForm, forms.Form):
        verified = forms.NullBooleanField(
            widget=genwidgets.NullBooleanSelect(choices=[
                ('unknown', 'Pending Review'),
                ('true', 'Verified'),
                ('false', 'Rejected'),
            ])
        )

-----------------
CheckboxInput
-----------------

A styled checkbox using Gentelella's flat checkbox style.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class TermsForm(GTForm, forms.Form):
        accept_terms = forms.BooleanField(
            widget=genwidgets.CheckboxInput,
            label='I accept the terms and conditions'
        )
        subscribe_newsletter = forms.BooleanField(
            widget=genwidgets.CheckboxInput,
            required=False,
            label='Subscribe to newsletter'
        )

----------------------
CheckboxSelectMultiple
----------------------

Multiple checkboxes for selecting several options from a list.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class InterestsForm(GTForm, forms.Form):
        interests = forms.MultipleChoiceField(
            choices=[
                ('tech', 'Technology'),
                ('sports', 'Sports'),
                ('music', 'Music'),
                ('art', 'Art'),
                ('travel', 'Travel')
            ],
            widget=genwidgets.CheckboxSelectMultiple
        )

    # For ModelForm with ManyToMany fields
    class UserProfileForm(GTForm, forms.ModelForm):
        class Meta:
            model = UserProfile
            fields = ['user', 'skills']
            widgets = {
                'skills': genwidgets.CheckboxSelectMultiple,
            }

---------------------------------
Using Select2 Inside Modals
---------------------------------

When using Select widgets inside Bootstrap modals, you need to specify the modal container to avoid dropdown display issues:

.. code:: python

    class ModalForm(GTForm, forms.ModelForm):
        class Meta:
            model = MyModel
            fields = ['category', 'tags']
            widgets = {
                'category': genwidgets.Select(attrs={
                    'data-dropdownparent': '#myModal'
                }),
                'tags': genwidgets.SelectMultiple(attrs={
                    'data-dropdownparent': '#myModal'
                }),
            }

In your template:

.. code:: html

    <div id="myModal" class="modal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-body">
                    {{ form.as_horizontal }}
                </div>
            </div>
        </div>
    </div>
