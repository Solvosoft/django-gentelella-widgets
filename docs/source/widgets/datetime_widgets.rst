Date and Time Widgets
^^^^^^^^^^^^^^^^^^^^^^^

Widgets for selecting dates, times, and date ranges with JavaScript-powered pickers.

.. note::

    For DateInput and DateTimeInput to work correctly, configure your Django settings:

    .. code:: python

        USE_L10N = False

        DATE_INPUT_FORMATS = ['%Y-%m-%d', '%d/%m/%Y', '%d/%m/%y']
        DATETIME_INPUT_FORMATS = ['%m/%d/%Y %H:%M %p']
        TIME_INPUT_FORMATS = ['%H:%M', '%H:%M:%S']

-----------------
DateInput
-----------------

A date picker widget with calendar popup.

.. code:: python

    from djgentelella.widgets import core as genwidgets
    from djgentelella.forms.forms import GTForm

    class EventForm(GTForm, forms.ModelForm):
        class Meta:
            model = Event
            fields = ['name', 'event_date', 'deadline']
            widgets = {
                'name': genwidgets.TextInput,
                'event_date': genwidgets.DateInput,
                'deadline': genwidgets.DateInput,
            }

The date format is automatically converted from Django's ``DATE_INPUT_FORMATS`` setting to the JavaScript picker format.

-----------------
DateTimeInput
-----------------

A combined date and time picker widget.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class MeetingForm(GTForm, forms.ModelForm):
        class Meta:
            model = Meeting
            fields = ['title', 'start_time', 'end_time']
            widgets = {
                'title': genwidgets.TextInput,
                'start_time': genwidgets.DateTimeInput,
                'end_time': genwidgets.DateTimeInput,
            }

-----------------
TimeInput
-----------------

A time-only picker widget.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class ScheduleForm(GTForm, forms.ModelForm):
        class Meta:
            model = Schedule
            fields = ['name', 'opening_time', 'closing_time']
            widgets = {
                'name': genwidgets.TextInput,
                'opening_time': genwidgets.TimeInput,
                'closing_time': genwidgets.TimeInput,
            }

-------------------
SplitDateTimeWidget
-------------------

Separate date and time inputs displayed side by side.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class AppointmentForm(GTForm, forms.Form):
        appointment = forms.SplitDateTimeField(
            widget=genwidgets.SplitDateTimeWidget
        )

-------------------------
SplitHiddenDateTimeWidget
-------------------------

Hidden split date and time inputs, useful for programmatic manipulation.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class HiddenDateTimeForm(GTForm, forms.Form):
        timestamp = forms.SplitDateTimeField(
            widget=genwidgets.SplitHiddenDateTimeWidget
        )

-----------------
SelectDateWidget
-----------------

Three dropdown selects for day, month, and year.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class BirthdayForm(GTForm, forms.Form):
        birth_date = forms.DateField(
            widget=genwidgets.SelectDateWidget
        )

-----------------
DateRangeInput
-----------------

.. image:: ../_static/DateRange.png

A calendar for selecting a range between two dates. Use with ``CharField`` or ``TextField``.

.. image:: ../_static/Date-range-input.gif

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class ReportForm(GTForm, forms.ModelForm):
        class Meta:
            model = Report
            fields = ['name', 'date_range']
            widgets = {
                'name': genwidgets.TextInput,
                'date_range': genwidgets.DateRangeInput,
            }

    # Or with a Form
    class FilterForm(GTForm, forms.Form):
        period = forms.CharField(widget=genwidgets.DateRangeInput)

The value is stored as a string in the format ``"start_date - end_date"``.

--------------------
DateRangeInputCustom
--------------------

A date range picker with preset options: Last 7 days, Next Week, Last 30 days, This month, Last month, and Custom Range.

.. image:: ../_static/Date-range-input-custom.gif

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class AnalyticsForm(GTForm, forms.Form):
        period = forms.CharField(widget=genwidgets.DateRangeInputCustom)

------------------
DateRangeTimeInput
------------------

A date range picker that also includes time selection.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class BookingForm(GTForm, forms.ModelForm):
        class Meta:
            model = Booking
            fields = ['room', 'reservation_period']
            widgets = {
                'room': genwidgets.Select,
                'reservation_period': genwidgets.DateRangeTimeInput,
            }

-----------------
DateMaskInput
-----------------

A date input with input masking to guide the user's input format.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class SimpleForm(GTForm, forms.Form):
        birth_date = forms.DateField(widget=genwidgets.DateMaskInput)

-----------------
DateTimeMaskInput
-----------------

A datetime input with input masking.

.. code:: python

    from djgentelella.widgets import core as genwidgets

    class LogForm(GTForm, forms.Form):
        log_time = forms.DateTimeField(widget=genwidgets.DateTimeMaskInput)

---------------------------------
Complete Example
---------------------------------

Here's a comprehensive example using multiple date/time widgets:

.. code:: python

    from django import forms
    from djgentelella.widgets import core as genwidgets
    from djgentelella.forms.forms import GTForm

    class EventScheduleForm(GTForm, forms.Form):
        # Single date selection
        event_date = forms.DateField(
            widget=genwidgets.DateInput,
            label='Event Date'
        )

        # Date and time selection
        start_datetime = forms.DateTimeField(
            widget=genwidgets.DateTimeInput,
            label='Start Date & Time'
        )

        # Time only
        check_in_time = forms.TimeField(
            widget=genwidgets.TimeInput,
            label='Check-in Time'
        )

        # Date range for multi-day events
        event_duration = forms.CharField(
            widget=genwidgets.DateRangeInput,
            label='Event Duration'
        )

        # Predefined date range options
        report_period = forms.CharField(
            widget=genwidgets.DateRangeInputCustom,
            label='Report Period'
        )

        # Date range with time
        booking_window = forms.CharField(
            widget=genwidgets.DateRangeTimeInput,
            label='Booking Window'
        )
