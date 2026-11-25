"""The ``forms`` section of a design, turned into GTForm classes at runtime.

Ported from djgentelella-editor (``gteditor.components.forms.build_form``),
with the same rules, but working on the model's fields instead of their JSON
description, and building a real class instead of code::

    "forms": {"cliente": {"model": "ventas.Cliente",
                          "fields": ["nombre", "pais"],
                          "render": "as_horizontal",
                          "widgets": {"pais": "AutocompleteSelect"},
                          "widget_options": {"nota": {"stars": 10}}}}

``widget_options`` sets the options of a field's widget (the one in
``widgets`` or its default), validated by the schema the widget declares in
:data:`djgentelella.forms.widgetmap.WIDGET_OPTIONS`: an option it does not
declare, a value out of its schema or options for a widget that takes none
are errors of the design, never keyword arguments passed as they come.

The model must be exposed (:mod:`djgentelella.designs.exposure`), every field
named must be one the exposure allows, and a relation must point to an exposed
model too: the GTForm never gets a model a design could not name itself.
"""

from dataclasses import dataclass, field
from functools import cached_property

from django import forms
from django.utils.translation import gettext as _

from djgentelella.forms import widgetmap
from djgentelella.forms.forms import GTForm
from djgentelella.groute import routes

RENDERS = ('as_horizontal', 'as_plain', 'as_inline', 'as_grid')


def camel(identifier):
    """``product_admin`` -> ``ProductAdmin``."""
    return ''.join(part[:1].upper() + part[1:] for part in identifier.split('_'))


def registered_lookups(model):
    """Basenames of the select2 lookups (``gtselects.py``) serving ``model``."""
    return sorted(basename for _prefix, viewset, basename in routes.registry
                  if getattr(viewset, 'model', None) is model)


def is_form_field(model_field):
    """Whether a ModelForm would show the field by default."""
    return model_field.editable and widgetmap.field_type(model_field) != 'auto'


def default_form(model, fields=None):
    """The ``forms`` entry of a design for ``model`` by default:
    ``{"model": "<app>.<Model>", "fields": [...]}`` with every field a
    ModelForm would show (:func:`is_form_field`), in the model's order --
    concrete fields, then many-to-many. Without ``widgets``: each field gets
    its default widget (:mod:`djgentelella.forms.widgetmap`).

    ``fields`` -- names, an exposure's for instance -- keeps only those.
    It is what djgentelella-editor imports for a model, and the form an
    ``object_management`` over the model needs.
    """
    opts = model._meta
    allowed = None if fields is None else set(fields)
    names = [model_field.name
             for model_field in list(opts.fields) + list(opts.many_to_many)
             if is_form_field(model_field)
             and (allowed is None or model_field.name in allowed)]
    return {'model': opts.label, 'fields': names}


@dataclass
class FormFieldBuild:
    name: str
    kind: str
    #: Key of :data:`djgentelella.forms.widgetmap.WIDGETS`.
    widget: str
    #: Basename of the select2 lookup an autocomplete widget is built with.
    lookup: str = None
    #: Options of the widget, validated (``widget_options`` of the form).
    options: dict = field(default_factory=dict)

    def widget_instance(self):
        if self.options:
            return widgetmap.build_widget(self.widget, self.options,
                                          lookup=self.lookup)
        widget_class = widgetmap.widget_class(self.widget)
        if self.widget in widgetmap.LOOKUP_WIDGETS:
            return widget_class(self.lookup)
        return widget_class


@dataclass
class FormBuild:
    key: str
    model: type
    render: str = 'as_horizontal'
    grid: list = None
    fields: list = field(default_factory=list)
    #: ``{field: {"title", "text"}}``: the text becomes the field's help_text.
    help: dict = field(default_factory=dict)

    @property
    def model_name(self):
        return self.model.__name__

    @property
    def class_name(self):
        return camel(self.key) + 'Form'

    @property
    def field_names(self):
        return [form_field.name for form_field in self.fields]

    @cached_property
    def form_class(self):
        """The GTForm ModelForm of this build, made once per build."""
        widgets, field_classes = {}, {}
        for form_field in self.fields:
            widgets[form_field.name] = form_field.widget_instance()
            if form_field.widget in widgetmap.TREE_FORM_FIELDS:
                field_classes[form_field.name] = \
                    widgetmap.TREE_FORM_FIELDS[form_field.widget]
        meta = type('Meta', (), {'model': self.model, 'fields': self.field_names,
                                 'widgets': widgets, 'field_classes': field_classes})
        attrs = {'__module__': __name__, 'Meta': meta}
        if self.grid:
            attrs.update(default_render_type='as_grid', grid_representation=self.grid)
        elif self.render != 'as_horizontal':
            attrs['default_render_type'] = self.render
        form_class = type(self.class_name, (GTForm, forms.ModelForm), attrs)
        for name, item in self.help.items():
            form_class.base_fields[name].help_text = item.get('text', '')
        return form_class

    def get_form(self, *args, preview=False, **kwargs):
        """An instance of :attr:`form_class`; with ``preview`` relations list
        no rows, the way the editor shows a design."""
        form = self.form_class(*args, **kwargs)
        if preview:
            for form_field in form.fields.values():
                if hasattr(form_field, 'queryset'):
                    form_field.queryset = form_field.queryset.none()
        return form


def _widget_for(build_path, form_field, model_field, widgets, rctx):
    """The widget key of ``model_field`` and its lookup, or ``None`` on error."""
    kind = widgetmap.field_kind(model_field)
    relation = kind in widgetmap.RELATION_KINDS
    is_tree = relation and widgetmap.is_tree_relation(model_field)
    lookups = rctx.lookups(model_field.related_model) if relation else []
    lookup = lookups[0] if lookups else None
    key = widgets.get(form_field)
    path = build_path + '.widgets.' + form_field
    if key is None:
        if is_tree:
            key = 'TreeSelectMultiple' if kind == 'm2m' else 'TreeSelect'
        else:
            usable = widgetmap.usable_widgets(kind, can_autocomplete=bool(lookup))
            key = usable[0] if usable else widgetmap.FALLBACK_WIDGETS[0]
        return key, lookup
    if key not in widgetmap.widget_choices(kind):
        rctx.error(path, _('%(widget)r cannot be used for a %(kind)s field; choose '
                           'one of %(choices)s') % {
            'widget': key, 'kind': kind,
            'choices': ', '.join(widgetmap.widget_choices(kind))})
        return None
    if key in widgetmap.TREE_WIDGETS and not is_tree:
        rctx.error(path, _('%(widget)s is for relations to a tree (TreeNode) '
                           'model; %(model)s is not one') % {
            'widget': key, 'model': model_field.related_model._meta.label})
        return None
    if key in widgetmap.LOOKUP_WIDGETS and lookup is None:
        rctx.error(path, _('%(widget)s needs a select2 lookup of %(model)s '
                           'registered in a gtselects.py') % {
            'widget': key, 'model': model_field.related_model._meta.label})
        return None
    return key, lookup


def _options_errors(build_path, name, widget, options, by_name, names, rctx):
    """Report the problems of ``options`` for the widget ``widget`` of the
    field ``name``: its schema, and what depends on the form -- the field
    kind of a range, the point field of a geocoded address."""
    path = build_path + '.widget_options.' + name
    if not isinstance(options, dict):
        rctx.error(path, _('the options of a widget must be an object'))
        return
    errors = widgetmap.validate_widget_options(widget, options, path)
    if errors:
        rctx.errors.extend(errors)
        return
    kind = widgetmap.field_kind(by_name[name])
    if widget == 'RangeInput' and kind == 'integer':
        for option in ('min_value', 'max_value', 'step'):
            value = options.get(option)
            if value is not None and value != int(value):
                rctx.error(path + '.' + option,
                           _('%s is an integer field: use a whole number') % name)
    if widget == 'GeocodedAddressInput' and options.get('point_field'):
        point = options['point_field']
        if point not in names or point not in by_name or \
                widgetmap.field_kind(by_name[point]) != 'point':
            rctx.error(path + '.point_field',
                       _('%r is not a point field of this form') % (point,))
    if widget == 'ComboboxInput':
        limit = getattr(by_name[name], 'max_length', None)
        for choice in options.get('choices') or []:
            value = choice[0] if isinstance(choice, list) else choice
            if limit and len(value) > limit:
                rctx.error(path + '.choices', _('%(value)r is longer than '
                                                'the %(limit)d characters of '
                                                '%(field)s') % {
                    'value': value, 'limit': limit, 'field': name})


def no_field(model_label, name):
    """The error of a field name that ``model_label`` does not let a design use."""
    return _('%(model)s has no field %(field)r a design may use') % {
        'model': model_label, 'field': name}


def build_form(key, data, rctx, path):
    """A :class:`FormBuild` for ``forms[key]``, or ``None`` after reporting errors.

    ``rctx`` is the :class:`~djgentelella.designs.components.ResolveContext`.
    """
    if not isinstance(data, dict):
        rctx.error(path, _('a form must be an object'))
        return None
    exposure = rctx.exposure(data.get('model'), path + '.model')
    if exposure is None:
        return None
    model = exposure.model
    by_name = {model_field.name: model_field
               for model_field in exposure.model_fields()}
    errors_before = len(rctx.errors)

    names = data.get('fields')
    if names is None:
        names = [name for name, model_field in by_name.items()
                 if is_form_field(model_field)]
    for name in names:
        if name not in by_name:
            rctx.error(path + '.fields', no_field(exposure.label, name))
        elif not is_form_field(by_name[name]):
            rctx.error(path + '.fields', _('%r is not editable') % (name,))
        elif by_name[name].is_relation:
            # Its choices list rows of the target: that model must be exposed.
            rctx.exposure(by_name[name].related_model._meta.label, path + '.fields')
    if len(set(names)) != len(names):
        rctx.error(path + '.fields', _('a field is listed twice'))

    grid = data.get('grid')
    render = data.get('render', 'as_grid' if grid else 'as_horizontal')
    if render not in RENDERS:
        rctx.error(path + '.render', _('%(value)r is not one of %(choices)s') % {
            'value': render, 'choices': ', '.join(RENDERS)})
    if render == 'as_grid' and not grid:
        rctx.error(path, _('render "as_grid" needs a "grid"'))
    if grid and render != 'as_grid':
        rctx.error(path + '.grid', _('a grid is only used with render "as_grid"'))
    if grid:
        placed = [name for row in grid for column in row for name in column]
        if sorted(placed) != sorted(names):
            rctx.error(path + '.grid',
                       _('the grid must place every form field exactly once '
                         '(GTForm does not render the fields it leaves out)'))

    widgets = data.get('widgets', {})
    for name in widgets:
        if name not in names:
            rctx.error(path + '.widgets', _('%r is not a field of this form') % (name,))
    for name in data.get('help', {}):
        if name not in names:
            rctx.error(path + '.help', _('%r is not a field of this form') % (name,))
    widget_options = data.get('widget_options') or {}
    if not isinstance(widget_options, dict):
        rctx.error(path + '.widget_options', _('must be an object'))
        widget_options = {}
    for name in widget_options:
        if name not in names:
            rctx.error(path + '.widget_options',
                       _('%r is not a field of this form') % (name,))
    if len(rctx.errors) > errors_before:
        return None

    build = FormBuild(key, model, render, grid, help=data.get('help', {}))
    for name in names:
        model_field = by_name[name]
        found = _widget_for(path, name, model_field, widgets, rctx)
        if found is None:
            continue
        widget, lookup = found
        options = widget_options.get(name)
        if options is not None:
            _options_errors(path, name, widget, options, by_name, names, rctx)
        build.fields.append(FormFieldBuild(
            name, widgetmap.field_kind(model_field), widget,
            lookup if widget in widgetmap.LOOKUP_WIDGETS else None,
            dict(options or {})))
    if len(rctx.errors) > errors_before:
        return None
    return build
