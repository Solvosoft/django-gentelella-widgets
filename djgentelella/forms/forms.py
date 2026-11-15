from django import forms
from django.forms import BaseFormSet, HiddenInput
from django.forms import BaseModelFormSet
from django.forms.formsets import DELETION_FIELD_NAME
from django.utils.safestring import mark_safe

from djgentelella.forms.dynamic import dynamic_attrs, dynamic_marker, flatatt


class GTForm(forms.Form):
    """
    GTForm is the basis of form management, it does the work of django
    `forms.Form`, including enhancements and boostrap rendering, so it should
    be inherited from this form, rather than `forms.Form`.

    Example of use:

    .. code:: python

         from djgentelella.forms.forms import GTForm
         class MyForm(GTForm):
              myfield = forms.TextField()

    Using with forms.ModelForm

    .. code:: python

         from djgentelella.forms.forms import GTForm
         class MyForm(GTForm, forms.ModelForm):
              myfield = forms.TextField()
              class Meta:
                model = MyModel

    Creating an instance and specify how render it.

    .. code:: python

        myform = myGTForm(render_type='as_inline', ... )

    """

    exposed_method = ('as_plain', 'as_inline', 'as_horizontal')
    default_render_type = None
    template_name_plain = 'forms/as_plain.html'
    template_name_inline = 'forms/as_inline.html'
    template_name_horizontal = 'forms/as_horizontal.html'
    template_name_grid = 'forms/as_grid.html'
    grid_representation = None
    # Dynamic actions (djgentelella.forms.dynamic.When rules). See
    # docs/source/dynamic_actions.rst.
    dynamic_actions = None
    # set_value(server=...) answers only authenticated users unless this is True.
    dynamic_actions_public = False
    # Permissions (user.has_perms) set_value(server=...) also requires.
    dynamic_actions_permissions = ()

    def __init__(self, *args, **kwargs):
        render_type = (
            self.default_render_type
            if self.default_render_type is not None
            else 'as_horizontal'
        )
        if 'render_type' in kwargs and hasattr(self, kwargs['render_type']):
            render_type = kwargs.pop('render_type')

        super().__init__(*args, **kwargs)

        # Per form, not on self.renderer: that is the renderer every form of
        # the process shares, so setting it there switched the template of
        # every form rendered after this one (a plain Form then rendered as
        # an empty grid).
        self._gt_template_name = getattr(
            self, 'template_name_' + render_type[3:], None) if \
            render_type.startswith('as_') else None
        if self._gt_template_name is None:
            self._gt_template_name = self.template_name_horizontal

    @property
    def template_name(self):
        return self._gt_template_name

    @template_name.setter
    def template_name(self, value):
        self._gt_template_name = value

    def get_dynamic_actions(self):
        """The rules this instance renders. Override to drop some per request;
        a server method still has to be declared in ``dynamic_actions``."""
        return list(self.dynamic_actions or ())

    @classmethod
    def dynamic_actions_has_permission(cls, request, method):
        """Whether ``request`` may run the server method ``method``.

        By default: an authenticated user (anyone with
        ``dynamic_actions_public``) holding ``dynamic_actions_permissions``.
        Override to check what the page of the form checks.
        """
        user = getattr(request, 'user', None)
        authenticated = user is not None and user.is_authenticated
        if not cls.dynamic_actions_public and not authenticated:
            return False
        perms = list(cls.dynamic_actions_permissions or ())
        if perms and not (authenticated and user.has_perms(perms)):
            return False
        return True

    @classmethod
    def dynamic_actions_instance(cls, request):
        """The instance the endpoint calls a ``set_value(server=...)`` method on.

        Override when ``__init__`` needs arguments (a user, an instance...).
        """
        return cls()

    @property
    def dynamic_actions_attrs(self):
        """``data-gt-dynamic*`` attributes for a ``<form>`` tag, for templates
        that render the fields one by one instead of ``{{ form }}`` (which
        already carries them)."""
        return flatatt(dynamic_attrs(self, self.get_dynamic_actions()))

    def render(self, template_name=None, context=None, renderer=None):
        html = super().render(template_name=template_name, context=context,
                              renderer=renderer)
        # BoundField.label_tag() renders through here too: only a whole form
        # carries the rules.
        if template_name is not None and template_name not in self._form_templates():
            return html
        marker = dynamic_marker(self, self.get_dynamic_actions())
        if marker:
            html = mark_safe(html + marker)
        return html

    # RenderableMixin binds both to its own render(): {{ form }} goes through
    # __html__ and would skip the rules.
    __str__ = render
    __html__ = render

    def _form_templates(self):
        return {
            self.template_name, self.template_name_plain,
            self.template_name_inline, self.template_name_horizontal,
            self.template_name_grid, self.template_name_div, self.template_name_p,
            self.template_name_table, self.template_name_ul,
        }

    def get_error_for_grid(self, name):
        if name in self.errors:
            return self.errors[name]
        return None

    @property
    def grid(self):
        """
        Example of return structure:

        .. code:: python

            [
                [ [forms.Field],[], [] ],
                [ [], [] ],
            ]

        """
        fields = []
        dic_fields = {}
        for name, bf in self._bound_items():
            if not bf.is_hidden:
                fields.append(bf)
                dic_fields[name] = bf

        if self.grid_representation is not None:
            grid = []  # self.grid_representation
            for row in self.grid_representation:
                col_list = []
                for col in row:
                    row_list = []
                    for field in col:
                        if field in dic_fields and dic_fields[field]:
                            row_list.append(
                                (dic_fields[field], self.get_error_for_grid(field))
                            )
                        else:
                            if hasattr(self, field):
                                row_list.append(
                                    (
                                        getattr(self, field)(),
                                        self.get_error_for_grid(field),
                                    )
                                )
                    col_list.append(row_list)
                grid.append(col_list)
            return grid
        return [[fields]]

    def as_plain(self):
        "Returns this form rendered as HTML using as_plain bootstrap approach."
        if hasattr(self, '_html_output'):
            return self._html_output(
                normal_row='<div class="as_plain"><div %(html_class_attr)s '
                + '>%(label)s%(errors)s%(field)s%(help_text)s</div></div>',
                error_row='%s',
                row_ender=' ',
                help_text_html='<br /><span class="helptext">%s</span>',
                errors_on_separate_row=False,
            )
        return self.render(self.template_name_plain)

    def as_inline(self):
        "Return this form rendered as HTML using as_inline bootstrap approach."
        if hasattr(self, '_html_output'):
            return self._html_output(
                normal_row='<div class="mb-4"><span class="">%(label)s</span>'
                + ' %(errors)s%(field)s%(help_text)s</div>',
                error_row='%s',
                row_ender='</div>',
                help_text_html=' <span class="helptext">%s</span>',
                errors_on_separate_row=False,
            )
        return self.render(self.template_name_inline)

    def as_horizontal(self):
        "Return this form rendered as HTML using as_horizontal bootstrap approach."
        if hasattr(self, '_html_output'):
            return self._html_output(
                normal_row='<div class="form-group row"><span class="col-sm-3">'
                + '%(label)s</span> <div class="col-sm-9 " '
                + '>%(errors)s%(field)s%(help_text)s</div></div>',
                error_row='%s',
                row_ender='</div>',
                help_text_html=' <span class="helptext">%s</span>',
                errors_on_separate_row=False,
            )
        return self.render(self.template_name_horizontal)

    def as_grid(self):
        """
        Allow you to arrange the form fields in rows and cols,
        When you use this render needs to fill  `grid_representation`
        attribute in your form
        Return this form rendered as HTML using grid bootstrap approach.,

        .. code:: python

            grid_representation=[
                [ ['key'],[], [] ],
                [ [], [] ],
            ]

        """
        return self.render(self.template_name_grid)

    def closediv(self):
        return '</div>'


class BaseFormset:
    def as_plain(self):
        forms = ' '.join(form.as_plain() for form in self)
        return mark_safe(str(self.management_form) + '\n' + forms)

    def as_inline(self):
        forms = ' '.join(form.as_inline() for form in self)
        return mark_safe(str(self.management_form) + '\n' + forms)

    def as_horizontal(self):
        forms = ' '.join(form.as_horizontal() for form in self)
        return mark_safe(str(self.management_form) + '\n' + forms)


class GTFormSet(BaseFormSet, BaseFormset):
    """
    This class Allow to manage FormSet using GTForm and Widgets,
    provide an implementation to integrate with django formset system.
    """

    ordering_widget = HiddenInput

    def add_fields(self, form, index):
        super().add_fields(form, index)
        if self.can_delete:
            form.fields[DELETION_FIELD_NAME].widget.attrs['class'] = 'invisible'
            form.fields[DELETION_FIELD_NAME].label = ''


class GTBaseModelFormSet(BaseModelFormSet):
    ordering_widget = HiddenInput

    def add_fields(self, form, index):
        super().add_fields(form, index)
        if self.can_delete:
            form.fields[DELETION_FIELD_NAME].widget.attrs['class'] = 'invisible'
            form.fields[DELETION_FIELD_NAME].label = ''


class UserBoundWidgetsMixin:
    """Gives the user of the request to the widgets that depend on it.

    A widget does not see the request; this mixin calls ``bind_user(user)``
    on every widget of the form that has it. Today those are the user-scoped
    upload widgets -- ``UserFileChunkedUpload`` and ``UserFileInput`` take
    only the user's own, finished uploads -- and the widgets with an "add"
    button and ``add_perms`` (``SelectWithAdd``, ``SelectMultipleAdd``,
    ``TreeSelectWithAdd``, ``TreeSelectMultipleWithAdd``,
    ``FilteredSelectMultiple``), which show it only to who holds those
    permissions. Put it before the form class::

        class DocumentForm(UserScopedUploadsMixin, GTForm, forms.ModelForm):
            class Meta:
                model = Document
                fields = ['file']
                widgets = {'file': UserFileChunkedUpload}

        form = DocumentForm(request.POST, user=request.user)
        # or DocumentForm(request.POST, request=request)

    A form that takes ``user`` for its own ends either passes it on
    (``super().__init__(*args, user=user, **kwargs)``) or keeps it as
    ``self.user`` (or ``self.request``): when no user was given, the mixin
    takes that one before the form is cleaned -- too late for rendering, so a
    form that shows an "add" button passes ``user=`` or ``request=``.
    :meth:`bind_upload_user` binds one explicitly. The subwidgets of a
    ``MultiWidget`` are bound too. Without a user the upload widgets take no
    upload at all and the ``add_perms`` widgets show no "add" button.
    """

    upload_user = None

    def __init__(self, *args, user=None, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is None and request is not None:
            user = getattr(request, 'user', None)
        self.bind_upload_user(user)

    def bind_upload_user(self, user):
        """Give ``user`` to every widget of the form that takes one."""
        self.upload_user = user
        for field in self.fields.values():
            self._bind_widget_user(field.widget, user)

    def _bind_widget_user(self, widget, user):
        bind = getattr(widget, 'bind_user', None)
        if callable(bind):
            bind(user)
        for subwidget in getattr(widget, 'widgets', None) or ():
            self._bind_widget_user(subwidget, user)

    def full_clean(self):
        if self.upload_user is None:
            user = getattr(self, 'user', None)
            if user is None:
                user = getattr(getattr(self, 'request', None), 'user', None)
            if user is not None:
                self.bind_upload_user(user)
        super().full_clean()


#: The name it had while only the upload widgets took a user.
UserScopedUploadsMixin = UserBoundWidgetsMixin
