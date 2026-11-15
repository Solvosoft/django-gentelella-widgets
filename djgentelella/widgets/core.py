import json

from django.forms import (
    PasswordInput as DJPasswordInput,
    FileInput as DJFileInput,
    ClearableFileInput as DJClearableFileInput,
    Textarea as DJTextarea,
    DateInput as DJDateInput,
    DateTimeInput as DJDateTimeInput,
    TimeInput as DJTimeInput,
    CheckboxInput as DJCheckboxInput,
    Select as DJSelect,
    SplitHiddenDateTimeWidget as DJSplitHiddenDateTimeWidget,
    CheckboxSelectMultiple as DJCheckboxSelectMultiple,
    SelectMultiple as DJSelectMultiple,
    SelectDateWidget as DJSelectDateWidget,
    SplitDateTimeWidget as DJSplitDateTimeWidget,
)
from django.forms.widgets import Input as DJInput
from django.urls import reverse_lazy
from django.utils import formats
from django.utils.translation import gettext as _

from djgentelella.chunked_upload.constants import COMPLETE
from djgentelella.models import ChunkedUpload


def js_widget_name(widget):
    """The ``data-widget`` of ``widget`` (an instance or a class): the name
    its javascript initializes it by.

    A subclass keeps the name of its base, so a widget subclassed in a
    project goes on working: the name is ``js_widget`` of the nearest class
    of the MRO that sets it, or else the name of the nearest class defined
    in djgentelella. A subclass that brings javascript of its own sets
    ``js_widget = 'MyWidget'``.

    The result is a :class:`JSWidgetName`: when the name is not the class's
    own, :func:`update_kwargs` also renders the class name as
    ``data-widget-class``, and the javascript initializes the widget by it if
    something registered that name in ``document.gtwidgets`` (a project
    subclass that ships its own javascript under its class name).
    """
    cls = widget if isinstance(widget, type) else type(widget)
    name = cls.__name__
    for klass in cls.__mro__:
        if 'js_widget' in vars(klass):
            name = klass.js_widget
            break
        if klass.__module__.partition('.')[0] == 'djgentelella':
            name = klass.__name__
            break
    return JSWidgetName(name, own=cls.__name__)


class JSWidgetName(str):
    """A ``data-widget`` value that remembers the class it was computed for."""

    def __new__(cls, name, own=None):
        value = super().__new__(cls, name)
        value.own = own or name
        return value


def upload_token(value):
    """The ``{"token": ...}`` dict an upload widget posts, or None."""
    try:
        token = json.loads(value)
    except (TypeError, ValueError):
        return None
    return token if isinstance(token, dict) else None


class UserUploadMixin:
    """For an upload widget: take only the uploads of ``user``, finished.

    The generic widgets resolve a token whoever uploaded the file, because
    who attaches or deletes a document does not have to be who uploaded it.
    With this mixin the token of another user, or of an upload that did not
    finish, gives no file and deletes nothing.

    The widget does not see the request: ``user`` is given to the widget
    (``UserFileChunkedUpload(user=...)``, :meth:`bind_user`) or, more often,
    by a form with :class:`~djgentelella.forms.forms.UserScopedUploadsMixin`.
    Without a user, no upload is taken.

    With ``keep_upload=True`` (or the class attribute) the field gets the
    ``ChunkedUpload`` itself and the upload is not deleted: for a form that
    keeps it for a later step, such as a data load that reads the file after
    the user maps its columns.
    """

    user = None
    #: Give the ``ChunkedUpload`` to the form, without deleting it.
    keep_upload = False

    def __init__(self, *args, user=None, keep_upload=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if keep_upload is not None:
            self.keep_upload = keep_upload

    def bind_user(self, user):
        self.user = user

    def upload_value(self, upload):
        if self.keep_upload:
            return upload
        return super().upload_value(upload)

    def get_upload(self, token):
        user = self.user
        if user is None or not user.is_authenticated:
            return None
        return ChunkedUpload.objects.filter(upload_id=token, user=user,
                                            status=COMPLETE).first()


def set_js_widget(attrs, name):
    """Put ``name`` (from :func:`js_widget_name`) in ``attrs`` as
    ``data-widget``, plus ``data-widget-class`` when the class has another
    name. ``attrs`` is changed and returned."""
    attrs['data-widget'] = str(name)
    own = getattr(name, 'own', None)
    if own and own != name:
        attrs['data-widget-class'] = own
    else:
        attrs.pop('data-widget-class', None)
    return attrs


def update_kwargs(attrs, widget, base_class='form-control '):
    if attrs is not None:
        attrs = attrs.copy()

    if attrs is None:
        attrs = {}
    if 'class' in attrs:
        attrs.update({'class': base_class + attrs['class']})
    else:
        attrs.update({'class': base_class})
    return set_js_widget(attrs, widget)


class Input(DJInput):
    """
    Base class for all <input> widgets.
    """

    template_name = 'gentelella/widgets/input.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self))
        super().__init__(attrs)


class TextInput(Input):
    input_type = 'text'
    template_name = 'gentelella/widgets/text.html'


class ColorInput(Input):
    input_type = 'color'
    template_name = 'gentelella/widgets/input.html'


class HiddenInput(Input):
    input_type = 'hidden'
    template_name = 'gentelella/widgets/text.html'


def GridSlider(attrs={}):
    class GridSlider(Input):
        input_type = 'text'
        template_name = 'gentelella/widgets/input.html'
        extra_attrs = attrs.copy()

        def __init__(self, attrs=None, extraskwargs=True):
            attrs = update_kwargs(attrs, js_widget_name(self))
            if self.extra_attrs:
                attrs.update(self.extra_attrs)
            super().__init__(attrs)

    return GridSlider


def DateGridSlider(attrs={}):
    class DateGridSlider(Input):
        input_type = 'text'
        template_name = 'gentelella/widgets/input.html'
        extra_attrs = attrs.copy()

        def __init__(self, attrs=None, extraskwargs=True):
            attrs = update_kwargs(attrs, js_widget_name(self))
            if self.extra_attrs:
                attrs.update(self.extra_attrs)
            super().__init__(attrs)

    return DateGridSlider


def SingleGridSlider(attrs={}):
    class SingleGridSlider(Input):
        input_type = 'text'
        template_name = 'gentelella/widgets/input.html'
        extra_attrs = attrs.copy()

        def __init__(self, attrs=None, extraskwargs=True):
            attrs = update_kwargs(attrs, js_widget_name(self))
            if self.extra_attrs:
                attrs.update(self.extra_attrs)
            super().__init__(attrs)

    return SingleGridSlider


class NumberInput(Input):
    input_type = 'number'
    template_name = 'gentelella/widgets/number.html'

    # min_value y max_value

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self))
        super().__init__(attrs, extraskwargs=extraskwargs)


class FloatInput(Input):
    input_type = 'number'
    template_name = 'gentelella/widgets/number.html'

    # min_value y max_value

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self))
        if 'step' not in attrs:
            attrs['step'] = '0.1'
        attrs['inputmode'] = 'decimal'
        super().__init__(attrs, extraskwargs=extraskwargs)


class EmailInput(Input):
    input_type = 'email'
    template_name = 'gentelella/widgets/email.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self))
        super().__init__(attrs, extraskwargs=extraskwargs)


class URLInput(Input):
    input_type = 'url'
    template_name = 'gentelella/widgets/url.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self))
        attrs['placeholder'] = 'https://'
        super().__init__(attrs, extraskwargs=extraskwargs)


class PasswordInput(DJPasswordInput):
    input_type = 'password'
    template_name = 'gentelella/widgets/password.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self))
        super().__init__(attrs)


# Fixme: do upload view


class FileInput(DJFileInput):
    input_type = 'file'
    needs_multipart_form = True
    template_name = 'gentelella/widgets/file.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(
                attrs,
                js_widget_name(self),
                base_class='djgentelella-file-input form-control',
            )
        if 'data-href' not in attrs:
            attrs.update({'data-href': reverse_lazy('upload_file_view')})
        if 'data-done' not in attrs:
            attrs['data-done'] = reverse_lazy('upload_file_done')
        super().__init__(attrs)

    def format_value(self, value):
        """File input never renders a value."""
        return

    def get_upload(self, token):
        """The ``ChunkedUpload`` of ``token``, **whoever uploaded it**.

        On purpose: who attaches the file does not have to be who uploaded
        it. :class:`UserFileInput` takes only the user's finished uploads.
        """
        return ChunkedUpload.objects.filter(upload_id=token).first()

    def upload_value(self, upload):
        """The value of the field for ``upload``: its file. The upload is
        deleted, so a token is used once."""
        dev = upload.get_uploaded_file()
        upload.delete()
        return dev

    def value_from_datadict(self, data, files, name):
        token = upload_token(data.get(name))
        if token is None or not isinstance(token.get('token'), str):
            return None
        upload = self.get_upload(token['token'])
        return self.upload_value(upload) if upload is not None else None

    def value_omitted_from_data(self, data, files, name):
        return name not in data


class UserFileInput(UserUploadMixin, FileInput):
    """:class:`FileInput` that takes only the uploads of its ``user``, and
    only once they finished (see :class:`UserUploadMixin`)."""

    js_widget = 'FileInput'


class ImageRecordInput(DJFileInput):
    """
    You can set the preview size using data-width and data-height.
    """

    needs_multipart_form = True
    template_name = 'gentelella/widgets/record_photo.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self), base_class='d-none')
        super().__init__(attrs)


class VideoRecordInput(DJFileInput):
    """
    You can set the preview size using data-width and data-height.

    .. note:: Size of video depends on camera default configuration.
    """

    needs_multipart_form = True
    template_name = 'gentelella/widgets/record_video.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self), base_class='d-none')
        super().__init__(attrs)


class AudioRecordInput(DJFileInput):
    needs_multipart_form = True
    template_name = 'gentelella/widgets/record_audio.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self), base_class='d-none')
        super().__init__(attrs)


class VoiceDictation(DJTextarea):
    """
    Textarea with a continuous dictation button: captures audio in the browser
    (Web Audio + VAD) and, as the user speaks, posts each speech segment to a
    transcription endpoint that returns ``{"text": "..."}``; segments are
    inserted live. ``data-mode`` selects the strategy: ``segments`` (default,
    live), ``single`` (one request on stop) or ``hybrid`` (live segments then a
    whole-file rewrite on stop).

    Two kwargs, the rest through ``attrs``: ``url`` is the transcription
    endpoint (``voice_transcribe`` or a proxy) and ``language`` sets
    ``data-language``. Everything else is configured with plain ``data-``
    attributes, which is deliberate -- the javascript reads them straight off
    the element, so a project can add its own without the widget growing a
    kwarg for each one, and a template can override one per field::

        VoiceDictation(url=reverse_lazy('voice_transcribe'),
                       language='es',
                       attrs={'data-mode': 'single'})

    The ones the shipped engine understands:

    :``data-mode``: dictation strategy -- ``segments`` (default, transcribes
        each speech segment live), ``single`` (one request when the user stops)
        or ``hybrid`` (live segments, then a whole-file rewrite on stop). An
        unknown value falls back to ``segments``.
    :``data-hotwords``: comma separated words to bias the recogniser towards.
    :``data-initial-prompt``: free text giving the recogniser context.

    Capture tuning, all numeric and all optional -- the defaults live in the
    engine, and these are the seven keys ``voiceVadConfig`` reads
    (``gentelella/js/base/voiceprogressive.js``):
    ``data-vad-silence-ms``, ``data-vad-min-speech-ms``,
    ``data-vad-max-segment-ms``, ``data-rms-threshold``, ``data-pool-size``,
    ``data-max-session-ms`` and ``data-request-timeout-ms``.

    ``hotwords`` and ``initial_prompt`` only reach a remote backend that was
    configured to accept them; the bundled Parakeet backend ignores both.
    """

    template_name = 'gentelella/widgets/voice_dictation.html'

    def __init__(self, attrs=None, extraskwargs=True, url=None, language=None):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self))
        attrs = attrs or {}
        if url is not None:
            attrs['data-url'] = url
        if language is not None:
            attrs['data-language'] = language
        super().__init__(attrs)


class ClearableFileInput(DJClearableFileInput):
    template_name = 'gentelella/widgets/file.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self))
        super().__init__(attrs)


class Textarea(DJTextarea):
    template_name = 'gentelella/widgets/textarea.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(
                attrs,
                js_widget_name(self),
                base_class='resizable_textarea form-control',
            )
        # update_kwargs is what normally turns None into a dict, so without
        # this `Textarea(extraskwargs=False)` died on the next line.
        attrs = attrs or {}
        attrs['rows'] = '3'
        super().__init__(attrs)


class DateFormatConverter:
    JS_FORMATS = {
        '%A': 'dddd',
        # Weekday as locale’s full name: (In English: Sunday, .., Saturday)(Auf
        # Deutsch: Sonntag, .., Samstag)
        '%a': 'ddd',
        # Weekday abbreivated: (In English: Sun, .., Sat)(Auf Deutsch: So, ..,
        # Sa)
        '%B': 'MMMM',
        # Month name: (In English: January, .., December)(Auf Deutsch: Januar,
        # .., Dezember)
        '%b': 'MMM',
        # Month name abbreviated: (In English: Jan, .., Dec)(Auf Deutsch: Jan,
        # .., Dez)
        '%c': 'ddd MMM DD HH:mm:ss YYYY',
        # Locale’s appropriate date and time representation: (English: Sun Oct
        # 13 23:30:00 1996)(Deutsch: So 13 Oct 22:30:00 1996)
        '%d': 'DD',  # Day 0 padded: (01, .., 31)
        '%f': 'SSS',  # Microseconds 0 padded: (000000, .., 999999)
        '%H': 'HH',  # Hour (24-Hour) 0 padded: (00, .., 23)
        '%I': 'hh',  # Hour (12-Hour) 0 padded: (01, .., 12)
        '%j': 'DDDD',  # Day of Year 0 padded: (001, .., 366)
        '%M': 'mm',  # Minute 0 padded: (01, .. 59)
        '%m': 'MM',  # Month 0 padded: (01, .., 12)
        '%p': 'A',  # Locale equivalent of AM/PM: (EN: AM, PM)(DE: am, pm)
        '%S': 'ss',  # Second 0 padded: (00, .., 59)
        '%U': 'ww',
        # Week  of Year (Sunday): (00, .., 53)  All days in a new year
        # preceding the first Sunday are considered to be in week 0.
        '%W': 'ww',
        # Week  of Year (Monday): (00, .., 53)  All days in a new year
        # preceding the first Monday are considered to be in week 0.
        '%w': 'd',  # Weekday as : (0, 6)
        '%X': 'HH:mm:ss',
        # Locale's appropriate time representation: (EN: 23:30:00)(DE:
        # 23:30:00)
        '%x': 'MM/DD/YYYY',
        # Locale's appropriate date representation: (None: 02/14/16)(EN:
        # 02/14/16)(DE: 14.02.16)
        '%Y': 'YYYY',  # Year as : (1970, 2000, 2038, 292,277,026,596)
        '%y': 'YY',  # Year without century 0 padded: (00, .., 99)
        '%Z': 'z',
        # Time zone name: ((empty), UTC, EST, CST) (empty string if the object
        # is naive).
        '%z': 'ZZ',
        # UTC offset in the form +HHMM or -HHMM: ((empty), +0000, -0400, +1030)
        # Empty string if the the object is naive.
        '%%': '%',  # A literal '%' character: (%)
    }

    def convert_python_to_js(self, value):
        for key in self.JS_FORMATS:
            js_key = self.JS_FORMATS[key]
            value = js_key.join(value.split(key))
        return value

    def get_format_js(self):
        self.format = formats.get_format(self.format_key)[0]
        return self.convert_python_to_js(self.format)


class DateInput(DJDateInput, DateFormatConverter):
    """
    .. warning::
        Set in settings

            USE_L10N = False

            DATE_INPUT_FORMATS=[ '%Y-%m-%d','%d/%m/%Y','%d/%m/%y']

        By limitation on js datetime widget format conversion
    """

    format_key = 'DATE_INPUT_FORMATS'
    template_name = 'gentelella/widgets/date.html'

    def __init__(self, attrs=None, format=None):
        attrs = update_kwargs(attrs, js_widget_name(self))
        format_js = self.get_format_js()
        attrs['data-format'] = format_js
        super().__init__(attrs, format=format or self.format)


class DateTimeInput(DJDateTimeInput, DateFormatConverter):
    """
    .. warning::
        Set in settings

            USE_L10N = False

            DATETIME_INPUT_FORMATS=[ '%m/%d/%Y %H:%M %p' ]

        By limitation on js datetime widget format conversion
    """

    format_key = 'DATETIME_INPUT_FORMATS'
    template_name = 'gentelella/widgets/datetime.html'

    def __init__(self, attrs=None, format=None):
        attrs = update_kwargs(attrs, js_widget_name(self))
        format_js = self.get_format_js()
        attrs['data-format'] = format_js
        super().__init__(attrs, format or self.format)


class TimeInput(DJTimeInput, DateFormatConverter):
    format_key = 'TIME_INPUT_FORMATS'
    template_name = 'gentelella/widgets/time.html'

    def __init__(self, attrs=None, format=None):
        attrs = update_kwargs(attrs, js_widget_name(self))
        format_js = self.get_format_js()
        attrs['data-format'] = format_js
        super().__init__(attrs, format or self.format)


class CheckboxInput(DJCheckboxInput):
    input_type = 'checkbox'
    template_name = 'gentelella/widgets/checkbox.html'

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, js_widget_name(self), base_class='gt-check ')
        super().__init__(attrs)
        self.format = format or None


class YesNoInput(DJCheckboxInput):
    input_type = 'checkbox'
    template_name = 'gentelella/widgets/checkyesno.html'

    def __init__(self, attrs=None, shparent='.form-group'):
        attrs = update_kwargs(attrs, js_widget_name(self), base_class='gt-switch ')

        if 'rel' in attrs:
            rel = attrs.pop('rel')
            attrs['data-rel'] = ';'.join(rel)
        if 'rel_start_hidden' in attrs:
            rel = attrs.pop('rel_start_hidden')
            attrs['data-relhidden'] = ';'.join(rel)
        attrs['data-shparent'] = shparent
        super().__init__(attrs)
        self.format = format or None


class Select(DJSelect):
    input_type = 'select'
    template_name = 'gentelella/widgets/select.html'
    option_template_name = 'gentelella/widgets/select_option.html'
    add_id_index = False
    checked_attribute = {'selected': True}
    option_inherits_attrs = False

    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(
                attrs,
                js_widget_name(self),
                base_class='select2_single form-control ',
            )
        super().__init__(attrs, choices=choices)


class AddPermissionMixin:
    """Shows the "add" button of a widget only to who may create the option.

    The ``*WithAdd`` widgets open a modal over ``add_url`` to create a catalog
    entry in place. ``add_perms`` (a permission or a list of them, given to the
    constructor or as ``attrs['add_perms']``) limits that button to the users
    holding all of them. A widget does not see the request, so the user comes
    from the form -- :class:`~djgentelella.forms.forms.UserBoundWidgetsMixin`
    calls :meth:`bind_user` -- and without one the button is not shown.

    ``can_add`` set to ``True`` or ``False`` overrides the permissions, for a
    form that decides it on its own.

    Hiding the button is only the interface: the view behind ``add_url`` has to
    require the same permissions.
    """

    #: ``None`` decides by ``add_perms``; ``True``/``False`` forces it.
    can_add = None
    add_perms = ()
    user = None

    def set_add_perms(self, attrs, add_perms=None):
        """Take ``add_perms`` from the argument or ``attrs``, out of the html."""
        attrs = dict(attrs or {})
        from_attrs = attrs.pop('add_perms', None)
        perms = add_perms if add_perms is not None else from_attrs
        if isinstance(perms, str):
            perms = (perms,)
        self.add_perms = tuple(perms or ())
        return attrs

    def bind_user(self, user):
        self.user = user

    def user_can_add(self):
        if self.can_add is not None:
            return bool(self.can_add)
        if not self.add_perms:
            return True
        user = self.user
        return bool(user is not None and user.is_authenticated
                    and user.has_perms(self.add_perms))

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['can_add'] = self.user_can_add()
        return context


class SelectWithAdd(AddPermissionMixin, Select):
    template_name = 'gentelella/widgets/addselect.html'
    option_template_name = 'gentelella/widgets/select_option.html'

    def __init__(self, attrs=None, choices=(), extraskwargs=True, add_perms=None):
        if extraskwargs:
            attrs = update_kwargs(
                attrs, js_widget_name(self), base_class='form-control '
            )
        if 'add_url' not in attrs:
            raise ValueError('SelectWithAdd requires add_url in attrs')
        attrs = self.set_add_perms(attrs, add_perms)
        super().__init__(attrs, choices=choices, extraskwargs=False)


class SelectMultiple(DJSelectMultiple):
    allow_multiple_selected = True

    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(
                attrs,
                js_widget_name(self),
                base_class='select2_multiple form-control ',
            )
        super(SelectMultiple, self).__init__(attrs, choices=choices)


class SelectMultipleAdd(AddPermissionMixin, SelectMultiple):
    allow_multiple_selected = True
    template_name = 'gentelella/widgets/addselect.html'
    option_template_name = 'gentelella/widgets/select_option.html'

    def __init__(self, attrs=None, choices=(), extraskwargs=True, add_perms=None):
        if extraskwargs:
            attrs = update_kwargs(
                attrs,
                js_widget_name(self),
                base_class='select2_multiple form-control ',
            )
        attrs = self.set_add_perms(attrs, add_perms)
        super(SelectMultipleAdd, self).__init__(
            attrs, choices=choices, extraskwargs=False
        )


class RadioHorizontalSelect(Select):
    input_type = 'radio'
    template_name = 'gentelella/widgets/radio.html'
    option_template_name = 'gentelella/widgets/attrs.html'

    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self), 'gtradio')
        super().__init__(attrs, choices=choices, extraskwargs=False)


class RadioVerticalSelect(Select):
    input_type = 'radio'
    template_name = 'gentelella/widgets/radio.html'
    option_template_name = 'gentelella/widgets/attrs.html'

    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self), 'gtradio')
        super().__init__(attrs, choices=choices, extraskwargs=False)

    def get_context(self, name, value, attrs):
        context = super(RadioVerticalSelect, self).get_context(name, value, attrs)
        context['widget']['br'] = True
        return context


RadioSelect = RadioHorizontalSelect


class NullBooleanSelect(RadioSelect):
    def __init__(
        self,
        attrs=None,
        choices=(
            ('unknown', _('Unknown')),
            ('true', _('Yes')),
            ('false', _('No')),
        ),
    ):
        attrs = update_kwargs(attrs, js_widget_name(self))
        super().__init__(attrs, choices=choices, extraskwargs=False)

    def format_value(self, value):
        try:
            return {
                True: 'true',
                False: 'false',
                'true': 'true',
                'false': 'false',
                # For backwards compatibility with Django < 2.2.
                '2': 'true',
                '3': 'false',
            }[value]
        except KeyError:
            return 'unknown'

    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        return {
            True: True,
            'True': True,
            'False': False,
            False: False,
            'true': True,
            'false': False,
            # For backwards compatibility with Django < 2.2.
            '2': True,
            '3': False,
        }.get(value)


class CheckboxSelectMultiple(DJCheckboxSelectMultiple):
    input_type = 'checkbox'
    template_name = 'gentelella/widgets/checkbox_select.html'
    option_template_name = 'gentelella/widgets/checkbox_option.html'

    def __init__(self, attrs=None, check_test=None):
        attrs = update_kwargs(attrs, js_widget_name(self), base_class='gt-check ')
        super().__init__(attrs)


class SplitDateTimeWidget(DJSplitDateTimeWidget):
    template_name = 'gentelella/widgets/splitdatetime.html'

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, js_widget_name(self))
        super().__init__(attrs)


class SplitHiddenDateTimeWidget(DJSplitHiddenDateTimeWidget):
    template_name = 'gentelella/widgets/splithiddendatetime.html'

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, js_widget_name(self))
        super().__init__(attrs)


class SelectDateWidget(DJSelectDateWidget):
    template_name = 'gentelella/widgets/select_date.html'

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, js_widget_name(self))
        super().__init__(attrs)


class DateMaskInput(DJDateInput):
    format_key = 'DATE_FORMAT'
    template_name = 'gentelella/widgets/date_input_mask.html'

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, js_widget_name(self))
        super().__init__(attrs)


class DateTimeMaskInput(DJDateTimeInput):
    format_key = 'DATETIME_INPUT_FORMATS'
    template_name = 'gentelella/widgets/datetime_input_mask.html'

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, js_widget_name(self))
        super().__init__(attrs)


class EmailMaskInput(TextInput):
    template_name = 'gentelella/widgets/email_input_mask.html'

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, js_widget_name(self))

        super().__init__(attrs)


class DateRangeTimeInput(DJDateTimeInput):
    format_key = 'DATETIME_INPUT_FORMATS'
    template_name = 'gentelella/widgets/daterangetime.html'

    def __init__(self, attrs=None, format=None):
        attrs = update_kwargs(attrs, js_widget_name(self))
        super().__init__(attrs, format=format)


class DateRangeInput(DJDateInput):
    format_key = 'DATE_INPUT_FORMATS'
    template_name = 'gentelella/widgets/daterange.html'

    def __init__(self, attrs=None, format=None):
        attrs = update_kwargs(attrs, js_widget_name(self))
        attrs['autocomplete'] = 'off'
        attrs['data-format'] = 'DD/MM/YYYY'
        super().__init__(attrs, format=format)


class DateRangeInputCustom(DJDateInput):
    format_key = 'DATE_INPUT_FORMATS'
    template_name = 'gentelella/widgets/daterange.html'

    def __init__(self, attrs=None, format=None):
        attrs = update_kwargs(attrs, js_widget_name(self))
        attrs['autocomplete'] = 'off'
        super().__init__(attrs, format=format)


class SerialNumberMaskInput(TextInput):
    input_type = 'text'
    template_name = 'gentelella/widgets/input_mask.html'

    def __init__(self, attrs=None, format=None):
        attrs = update_kwargs(attrs, js_widget_name(self))
        super().__init__(attrs)


class TaxIDMaskInput(TextInput):
    input_type = 'text'
    template_name = 'gentelella/widgets/input_mask.html'

    def __init__(self, attrs=None, format=None):
        attrs = update_kwargs(attrs, js_widget_name(self))
        super().__init__(attrs)


class CreditCardMaskInput(TextInput):
    input_type = 'text'
    template_name = 'gentelella/widgets/input_mask.html'

    def __init__(self, attrs=None, format=None):
        attrs = update_kwargs(attrs, js_widget_name(self))
        super().__init__(attrs)


class PhoneNumberTwoDigitMaskInput(TextInput):
    input_type = 'text'
    template_name = 'gentelella/widgets/phone_number_input_mask.html'

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, js_widget_name(self))

        super().__init__(attrs)


class PhoneNumberMaskInput(TextInput):
    input_type = 'text'
    template_name = 'gentelella/widgets/phone_number_input_mask.html'

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, js_widget_name(self))

        super().__init__(attrs)


class PhoneNumberMaskInput(TextInput):
    input_type = 'text'
    template_name = 'gentelella/widgets/phone_number_input_mask.html'

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, js_widget_name(self))

        super().__init__(attrs)
