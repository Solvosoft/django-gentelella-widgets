"""The components with data: tables, charts, stats, the classic CRUD, facets.

Ported from djgentelella-editor (``gteditor.components.builtin``,
``dashboard`` and ``classic``), with the same validation, but serving the
node instead of generating code: :meth:`resolve` returns a build of
:mod:`djgentelella.designs.builds`, :meth:`render` writes the final HTML and
:meth:`endpoints` hands the design router the viewsets
:mod:`djgentelella.designs.factories` makes from the build.

=============================  ==============================================
``object_management``          a DataTable with create, update, detail and
                               delete modals (``ObjectCRUD``)
``inline_object_management``   the same over the children of the page's
                               parent object (``meta.parent``)
``chart``                      Chart.js (``DJGraph``): one aggregate grouped
                               by a field or a date period, of a model or of a
                               data source
``stat``                       one number, optionally against the previous
                               period
``crud_classic``               djgentelella's ``CRUDView``: its list in the
                               page, or a link to its pages
``facets``                     a facets panel that filters another table
=============================  ==============================================

Only exposed models are accepted, and of them only the fields their exposure
allows; every endpoint checks ``AllPermissionByAction`` with the permissions
of the build.
"""

import copy

from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils.html import escape, json_script
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from rest_framework.exceptions import APIException

from djgentelella.authorization import evaluate_condition, validate_condition
from djgentelella.datasources.base import get_datasource
from djgentelella.designs import conditions, factories, format
from djgentelella.designs.builds import (
    ACTION_PERMISSIONS, AGGREGATES, CHART_TYPES, CRUD_PERMISSIONS, CRUD_VIEWS,
    PERIODS, TABLE_ACTIONS, ChartBuild, CrudBuild, FacetsBuild, ObjectManagementBuild,
    RowLink, StatBuild,
)
from djgentelella.designs.components import Endpoint, RuntimeComponent
from djgentelella.designs.conditions import (
    check_conditions, conditions_schema, denied, hidden_columns,
)
from djgentelella.designs.forms import build_form, no_field
from djgentelella.designs.introspection import (
    NUMBER_KINDS, TEXT_KINDS, column_type, describe_field,
)
from djgentelella.designs.models import Page, normalize_path
from djgentelella.designs.notifications import NOTIFY_SCHEMA, resolve_notify
from djgentelella.forms import widgetmap
from djgentelella.permission_management import all_permission

__all__ = ['ChartComponent', 'CrudClassicComponent', 'DATA_COMPONENTS',
           'FLOW_PREFIX', 'FacetsComponent', 'InlineObjectManagementComponent',
           'ObjectManagementComponent', 'PAGE_PREFIX', 'PK_PLACEHOLDERS',
           'StatComponent', 'parse_flow_link', 'resolve_row_link']

SCRIPT = 'gentelella/js/designs/data_components.js'
PERMISSION = {'type': 'string', 'pattern': r'^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$'}
PERMISSION_LIST = {'type': 'array', 'items': PERMISSION}
SINGLE_RELATIONS = ('fk', 'o2o')
DATE_KINDS = ('date', 'datetime')
#: A row link's URL is reversed with this in place of the pk; the browser
#: puts the row's pk there.
PK_PLACEHOLDERS = ('987654321', 'gtdesignpk')
#: What a table table's column cannot show.
NOT_LISTABLE = ('json', 'binary', 'point', 'other')
TABLE_TYPES = ('object_management', 'inline_object_management')


def label(text):
    return capfirst(str(text))


def plural(model):
    return label(model._meta.verbose_name_plural)


def page_hash(rctx):
    """The hash of the document being resolved, the factories' cache key."""
    if '_gtdesign_hash' not in rctx.__dict__:
        rctx._gtdesign_hash = format.document_hash(rctx.design)
    return rctx._gtdesign_hash


def data_build(build_class, node, rctx, **kwargs):
    return build_class(node['id'], node['type'], dict(node.get('props') or {}),
                       page_hash=page_hash(rctx), preview=rctx.preview, **kwargs)


def kind_of(model_field):
    return widgetmap.field_kind(model_field)


def check_permissions(rctx, path, perms):
    """Each permission exists; an empty list is refused (it would deny all).

    Kept for callers of the module function: the check is the context's,
    :meth:`~djgentelella.designs.components.ResolveContext.check_permissions`.
    """
    return rctx.check_permissions(path, perms)


def check_relation(rctx, path, model_field):
    """A relation shows its target's rows: that model must be exposed too."""
    if model_field.is_relation:
        rctx.exposure(model_field.related_model._meta.label, path)


def allowed_fields(found):
    return {model_field.name: model_field for model_field in found.model_fields()}


def form_mismatch(props, form):
    """The error of a ``props.form`` whose model is not ``props.model``."""
    return _('form %(form)r is for %(model)s, not %(expected)s') % {
        'form': props['form'], 'model': form.model._meta.label,
        'expected': props['model']}


def columns_of(found):
    return factories.allowed_columns(found.model, found.model_fields())


def endpoint_url(rctx, build, *parts):
    """The URL of the node's endpoint for the page being rendered, or None
    while there is no page (validation, the editor's preview)."""
    page = getattr(rctx.request, 'gtdesign_page', None)
    if page is None:
        return None
    rest = ''.join('%s/' % part for part in parts)
    return reverse('gt-design-endpoint', kwargs={
        'page_id': page.pk, 'node_id': build.id, 'rest': rest})


def condition_object(rctx, build):
    """The object the conditions inside the component of ``build`` are
    evaluated with: the one of a page about one object (``meta.parent``)
    when its endpoints carry it, or ``None`` -- what its API will use too
    (:meth:`djgentelella.designs.engine.ResolvedPage.condition_object`)."""
    parent = getattr(rctx.request, 'gtdesign_parent', None)
    if parent is None:
        return None
    resolved = rctx.resolved or getattr(rctx.request, 'gtdesign_resolved', None)
    if resolved is not None and getattr(build, 'id', None) in resolved.nodes:
        return resolved.condition_object(build.id, parent)
    return conditions.condition_object(build, rctx.request)


def can(rctx, perms):
    user = rctx.user
    return user is not None and all_permission(user, list(perms))


def no_permission(build):
    return render_to_string('gtdesigns/components/no_permission.html', {'b': build})


def json_config(element_id, data):
    """``data`` in a ``<script type="application/json">``: never code."""
    return json_script(data, element_id)


# -- row links -----------------------------------------------------------------------

def reverse_with_placeholder(url_name):
    """``(url, placeholder)`` of a URL name that takes one pk, or None."""
    for placeholder in PK_PLACEHOLDERS:
        for args, kwargs in (([placeholder], {}), ([], {'pk': placeholder})):
            try:
                return reverse(url_name, args=args, kwargs=kwargs), placeholder
            except NoReverseMatch:
                continue
    return None


#: A row link to a design page by its path: ``page:<path>``.
PAGE_PREFIX = 'page:'
#: A row link to a flow: ``flow:<name>[:<transition>]``.
FLOW_PREFIX = 'flow:'


def design_page_for(name):
    """The path of a design page a row link names, or None.

    ``page:<path>`` names it by path; a bare name is the ``meta.url_name``
    of a published page.
    """
    if name.startswith(PAGE_PREFIX):
        path = normalize_path(name[len(PAGE_PREFIX):])
        page = Page.objects.filter(path=path).first()
    else:
        page = Page.objects.filter(document__meta__url_name=name).first()
    return page


def parse_flow_link(text, known=None):
    """``(flow name, transition)`` of a ``flow:<name>[:<transition>]`` row
    link, or ``None`` when ``text`` is not one; ``transition`` is ``''`` for
    a link to the flow itself.

    It only reads the text. A flow name may hold ``:`` too, so ``known``,
    when given, is asked ``known(name) -> bool`` whether the whole text after
    the prefix is a flow before it is split at its last ``:``. Without it,
    the last ``:`` always starts the transition.
    """
    if not isinstance(text, str) or not text.startswith(FLOW_PREFIX):
        return None
    spec = text[len(FLOW_PREFIX):]
    if not spec:
        return None
    if ':' not in spec or (known is not None and known(spec)):
        return spec, ''
    name, _colon, transition = spec.rpartition(':')
    return (name, transition) if name else None


def flows_installed():
    return apps.is_installed('djgentelella.flows')


def find_flow(rctx, name):
    """The flow of djgentelella.flows called ``name`` for the design's site,
    or ``None``. A name without a dot is one of the design's ``app``, the way
    djgentelella-editor names the flows it designs (``<app>.<slug>``)."""
    # Optional app: only importable when it is installed (checked first).
    from djgentelella.flows.base import get_flow  # noqa: PLC0415
    flow = get_flow(name, site=rctx.site)
    if flow is None and '.' not in name and rctx.design.get('app'):
        flow = get_flow('%s.%s' % (rctx.design['app'], name), site=rctx.site)
    return flow


def resolve_flow_link(rctx, where, model, name):
    """``(flow name, transition)`` of a ``flow:<name>[:<transition>]`` row
    link, or ``None`` after reporting why it cannot be one."""
    if not flows_installed():
        rctx.error(where, _('%r needs djgentelella.flows in INSTALLED_APPS') % (name,))
        return None
    flows = {}

    def known(flow_name):
        flows[flow_name] = find_flow(rctx, flow_name)
        return flows[flow_name] is not None

    parsed = parse_flow_link(name, known)
    flow, transition = None, ''
    if parsed is not None:
        flow_name, transition = parsed
        if flow_name not in flows:
            flows[flow_name] = find_flow(rctx, flow_name)
        flow = flows[flow_name]
    if flow is None:
        rctx.error(where, _('%(link)r: no flow %(flow)r (djgentelella.flows)') % {
            'link': name, 'flow': name[len(FLOW_PREFIX):]})
        return None
    if flow.model is not model:
        rctx.error(where, _('flow %(flow)r is about %(model)s, not %(page)s') % {
            'flow': flow.name, 'model': flow.model._meta.label,
            'page': model._meta.label})
        return None
    if transition:
        step = flow.get_transition(transition)
        if step is None or step.auto:
            rctx.error(where, _('flow %(flow)r has no transition %(transition)r '
                                'a user can run') % {'flow': flow.name,
                                                     'transition': transition})
            return None
    return flow.name, transition


def resolve_row_link(rctx, link, model, path):
    """The :class:`~djgentelella.designs.builds.RowLink` of one row link of
    a table over ``model``, or ``None`` after reporting (at ``path``) why it
    cannot be one.

    What :meth:`ResolveContext.row_link
    <djgentelella.designs.components.ResolveContext.row_link>` does by
    default: a URL name of the project that takes one pk, a published design
    page (``page:<path>`` or its ``meta.url_name``) about one ``model``, or a
    flow of djgentelella.flows (``flow:<name>[:<transition>]``).
    """
    name = link['url_name']
    condition = link.get('condition')
    icon = link.get('icon') or 'fa fa-external-link'
    if name.startswith(FLOW_PREFIX):
        found = resolve_flow_link(rctx, path, model, name)
        if found is None:
            return None
        return RowLink(link['title'], icon, flow=found[0], transition=found[1],
                       condition=condition)
    if not name.startswith(PAGE_PREFIX) and reverse_with_placeholder(name):
        return RowLink(link['title'], icon, url_name=name, condition=condition)
    page = design_page_for(name)
    if page is None:
        rctx.error(path, _('%r is neither a URL name of the project that takes '
                           'one pk, a design page ("page:<path>" or its '
                           'meta.url_name) nor a flow ("flow:<name>")') % (name,))
        return None
    parent = ((page.document.get('meta') or {}).get('parent') or {}).get('model')
    if not isinstance(parent, str) or parent.lower() != model._meta.label_lower:
        rctx.error(path, _('design page %(page)r is not a page of one '
                           '%(model)s (its meta.parent)') % {
            'page': page.path, 'model': model._meta.label})
        return None
    return RowLink(link['title'], icon, page=page.path, condition=condition)


def resolve_row_links(rctx, path, model, links):
    """The row links of the table at ``path``: each one's condition is
    checked here, and the link itself is asked to ``rctx.row_link()``."""
    result = []
    for index, link in enumerate(links):
        where = '%s.props.row_links[%d]' % (path, index)
        condition = link.get('condition')
        if condition is not None:
            errors = validate_condition(condition, where + '.condition')
            if errors:
                rctx.errors.extend(errors)
                continue
        found = rctx.row_link(link, model, where)
        if found is not None:
            result.append(found)
    return result


def flow_link_url(link):
    """``(url, placeholder)`` of a ``flow:`` row link, or ``None`` when
    djgentelella.flows does not serve it."""
    placeholder = PK_PLACEHOLDERS[0]
    try:
        if link.transition:
            return reverse('flow_transition', args=[
                link.flow, link.transition, placeholder]), placeholder
        return reverse('flow_detail', args=[link.flow, placeholder]), placeholder
    except NoReverseMatch:
        return None


def row_link_config(build, request=None, obj=None):
    """The row links of a table for ``request``: those whose condition holds
    (with ``obj``, the object of a page about one)."""
    links = []
    for index, link in enumerate(build.row_links):
        if link.condition is not None and not evaluate_condition(
                link.condition, request, obj):
            continue
        if link.page:
            placeholder = PK_PLACEHOLDERS[0]
            url = reverse('gt-design-page', args=['%s/%s' % (link.page, placeholder)])
        else:
            found = flow_link_url(link) if link.flow else \
                reverse_with_placeholder(link.url_name)
            if found is None:
                continue
            url, placeholder = found
        links.append({'name': 'link%d' % index, 'title': escape(link.title),
                      'i_class': escape(link.icon), 'url': url,
                      'placeholder': placeholder})
    return links


# -- object management ---------------------------------------------------------------

def table_columns(build, hidden=()):
    """The DataTables columns of a table, as JSON-friendly data, without the
    ``hidden`` ones (their condition does not hold)."""
    columns = []
    for name in build.list_fields:
        if name in hidden:
            continue
        model_field = build.model._meta.get_field(name)
        kind = kind_of(model_field)
        lookup = build.lookups.get(name)
        column = {'data': name, 'name': name, 'kind': kind,
                  'title': escape(label(model_field.verbose_name)),
                  'type': column_type(describe_field(model_field), bool(lookup))}
        if kind == 'choices':
            column['choices'] = [[value, escape(str(text))]
                                 for value, text in model_field.flatchoices]
        if kind == 'm2m' and lookup:
            column['multiple'] = True
        if lookup:
            try:
                column['url'] = reverse(lookup + '-list')
            except NoReverseMatch:
                # A lookup a context offered that the project does not serve
                # (yet): the column is not filtered by an autocomplete.
                pass
        columns.append(column)
    return columns


def sample_value(model_field, index):
    kind = kind_of(model_field)
    if kind in NUMBER_KINDS:
        return str(index * 10)
    if kind == 'boolean':
        return _('Yes') if index % 2 else _('No')
    if kind == 'choices':
        choices = list(model_field.flatchoices)
        return str(choices[index % len(choices)][1]) if choices else ''
    if kind in DATE_KINDS:
        return '2026-0%d-1%d' % (index, index)
    return '%s %d' % (label(model_field.verbose_name), index)


def sample_rows(model, names, count=3):
    """Example rows for the editor's preview: no row is ever read."""
    fields = [model._meta.get_field(name) for name in names]
    return [[sample_value(model_field, index) for model_field in fields]
            for index in range(1, count + 1)]


class ObjectManagementComponent(RuntimeComponent):
    """A DataTable of a model with create, update, detail and delete modals.

    The djgentelella "object management" pattern: an
    ``AuthAllPermBaseObjectManagement`` viewset (permission checked per
    action), its serializers and FilterSet -- all made at runtime -- and
    ``ObjectCRUD`` in the page.
    """

    type = 'object_management'
    label = gettext_lazy('Object management (CRUD table)')
    icon = 'fa fa-table'
    props_schema = {
        'type': 'object',
        'required': ['model', 'form'],
        'additionalProperties': False,
        'properties': {
            'model': {'type': 'string', 'x-widget': 'model', 'title': 'Model'},
            'form': {'type': 'string', 'x-widget': 'form', 'title': 'Form',
                     'description': 'Key in the design "forms".'},
            'title': {'type': 'string', 'title': 'Title'},
            'list_fields': {'type': 'array', 'items': {'type': 'string'},
                            'minItems': 1, 'x-widget': 'model-fields',
                            'title': 'Table columns'},
            'search_fields': {'type': 'array', 'items': {'type': 'string'},
                              'x-widget': 'model-text-fields',
                              'title': 'Searched by the table search box'},
            'ordering': {'type': 'array', 'items': {'type': 'string'},
                         'title': 'Ordering (e.g. -pk)'},
            'perms': {
                'type': 'object',
                'x-widget': 'perms',
                'title': 'Permissions per action (empty = the model ones)',
                'additionalProperties': False,
                'properties': {action: PERMISSION_LIST
                               for action in ACTION_PERMISSIONS},
            },
            'notify': NOTIFY_SCHEMA,
            'column_conditions': conditions_schema(
                'Columns shown only when (by field)'),
            'action_conditions': conditions_schema(
                'Actions allowed only when', list(TABLE_ACTIONS)),
            'row_links': {
                'type': 'array',
                'x-widget': 'links',
                'title': 'Row links to pages about one object',
                'items': {
                    'type': 'object',
                    'required': ['url_name', 'title'],
                    'additionalProperties': False,
                    'properties': {'url_name': {
                                       'type': 'string', 'minLength': 1,
                                       'description': 'A URL name taking the row '
                                       'pk, "page:<path>" or "flow:<name>"'
                                       '[":<transition>"]'},
                                   'title': {'type': 'string'},
                                   'icon': {'type': 'string'},
                                   'condition': {'x-widget': 'condition',
                                                 'title': 'Shown only when'}},
                },
            },
        },
    }

    def resolve(self, node, rctx, path):
        return self.resolve_management(node, rctx, path)

    def resolve_management(self, node, rctx, path, parent_field=None,
                           parent_model=None, parent_perms=()):
        props = node.get('props') or {}
        build = data_build(ObjectManagementBuild, node, rctx,
                           parent_field=parent_field, parent_model=parent_model,
                           parent_perms=list(parent_perms))
        found = rctx.exposure(props['model'], path + '.props.model')
        form = rctx.form(props['form'], path + '.props.form')
        if found is None or form is None:
            return build
        model = found.model
        if form.model is not model:
            rctx.error(path + '.props.form', form_mismatch(props, form))
            return build
        by_name = allowed_fields(found)

        list_names = props.get('list_fields') or [
            name for name in form.field_names
            if kind_of(by_name[name]) not in ('text', 'file', 'image', 'json')
            and name != parent_field][:6]
        for name in list_names:
            if name not in by_name:
                rctx.error(path + '.props.list_fields',
                           no_field(props['model'], name))
            elif kind_of(by_name[name]) in NOT_LISTABLE:
                rctx.error(path + '.props.list_fields',
                           _('%r cannot be a table column') % (name,))
            else:
                check_relation(rctx, path + '.props.list_fields', by_name[name])
        search = props.get('search_fields')
        if search is None:
            search = [name for name in list_names if name in by_name
                      and kind_of(by_name[name]) in TEXT_KINDS]
        for name in search:
            if name not in by_name or kind_of(by_name[name]) not in TEXT_KINDS:
                rctx.error(path + '.props.search_fields',
                           _('%(field)r is not a text field of %(model)s') % {
                               'field': name, 'model': props['model']})
        ordering = props.get('ordering', ['-pk'])
        for name in ordering:
            if name.lstrip('-') not in set(by_name) | {'pk'} or \
                    (name.lstrip('-') in by_name
                     and kind_of(by_name[name.lstrip('-')]) == 'm2m'):
                rctx.error(path + '.props.ordering', _('unknown field %r') % (name,))

        perms = {action: found.permissions(permission)
                 for action, permission in ACTION_PERMISSIONS.items()}
        perms.update(props.get('perms', {}))
        for action, needed in perms.items():
            check_permissions(rctx, path + '.props.perms.' + action, needed)
        if model._meta.pk.name != 'id' and 'id' in by_name:
            rctx.error(path + '.props.model', _('%s has a field "id" that is not '
                                                'its primary key: the table needs '
                                                '"id" for the row') % props['model'])
        row_links = resolve_row_links(rctx, path, model, props.get('row_links', []))
        column_conditions = check_conditions(
            rctx, path + '.props.column_conditions', props.get('column_conditions'),
            list(list_names), _('column'))
        action_conditions = check_conditions(
            rctx, path + '.props.action_conditions', props.get('action_conditions'),
            list(TABLE_ACTIONS), _('action'))
        notify = None
        if props.get('notify'):
            notify = resolve_notify(rctx, path, model, props['notify'])
        if rctx.has_errors_under(path):
            return build

        lookups = {}
        for name in list_names:
            model_field = by_name[name]
            if model_field.is_relation:
                basenames = rctx.lookups(model_field.related_model)
                if basenames:
                    lookups[name] = basenames[0]
        build.title = props.get('title') or plural(model)
        build.model = model
        build.form = form
        build.list_fields = list(list_names)
        build.search_fields = list(search)
        build.ordering = list(ordering)
        build.perms = perms
        build.row_links = row_links
        build.notify = notify
        build.lookups = lookups
        build.columns = columns_of(found)
        build.column_conditions = column_conditions
        build.action_conditions = action_conditions
        return build

    def base_url(self, build, rctx):
        if build.inline:
            parent = getattr(rctx.request, 'gtdesign_parent', None)
            if parent is None:
                return None
            return endpoint_url(rctx, build, parent.pk)
        return endpoint_url(rctx, build)

    def render(self, build, rctx, children):
        if build.model is None:
            return mark_safe('')
        if rctx.preview:
            return render_to_string('gtdesigns/components/object_management.html', {
                'b': build, 'preview': True,
                'columns': [table_columns(build)[index]['title']
                            for index in range(len(build.list_fields))],
                'rows': sample_rows(build.model, build.list_fields)})
        if not can(rctx, build.perms['list']):
            return no_permission(build)
        base = self.base_url(build, rctx)
        if base is None:
            return no_permission(build)
        prefix = build.id
        obj = condition_object(rctx, build)
        refused = denied(build, rctx.request, obj)
        hidden = hidden_columns(build, rctx.request, obj)
        allowed = {action: can(rctx, build.perms[action]) and action not in refused
                   for action in ('create', 'update', 'destroy', 'retrieve')}
        modal_ids = {}
        forms = {}
        if allowed['create']:
            modal_ids['create'] = '#%s_create_modal' % prefix
            forms['create'] = build.form.get_form(prefix=prefix + '_create')
        if allowed['update']:
            modal_ids['update'] = '#%s_update_modal' % prefix
            forms['update'] = build.form.get_form(prefix=prefix + '_update')
            # An update neither shows nor writes a hidden column (its API
            # leaves it out too).
            for name in hidden:
                forms['update'].fields.pop(name, None)
        if allowed['retrieve']:
            modal_ids['detail'] = '#%s_detail_modal' % prefix
        if allowed['destroy']:
            modal_ids['destroy'] = '#%s_delete_modal' % prefix
        config = {
            'id': build.id,
            'urls': {
                'list_url': base,
                'create_url': base,
                'update_url': base + '0/',
                'destroy_url': base + '0/',
                'detail_url': base + '0/',
                'detail_template_url': base + 'detail_template/',
                'get_values_for_update_url': base + '0/get_values_for_update/',
            },
            'modal_ids': modal_ids,
            'columns': table_columns(build, hidden),
            'row_links': row_link_config(build, rctx.request, obj),
            'delete_display': factories.delete_display(build),
        }
        return render_to_string('gtdesigns/components/object_management.html', {
            'b': build, 'forms': forms, 'base': base, 'modal_ids': modal_ids,
            'allowed': allowed,
            'config': json_config(build.id + '_gtconfig', config),
        }, request=rctx.request)

    def media(self, build, rctx):
        return {'js': [SCRIPT]}

    def endpoints(self, build):
        if build.model is None:
            return []
        viewset = factories.management_viewset_for(build)
        suffix = r'(?P<parent_pk>[^/.]+)' if build.inline else ''
        return [Endpoint(suffix, viewset, 'gtdesign-%s' % build.id)]


class InlineObjectManagementComponent(ObjectManagementComponent):
    """The CRUD table of the children of the page's parent object.

    Needs ``meta.parent`` on the page, which is then served at
    ``designs/<path>/<parent pk>``. The viewset is a
    ``BaseInlineObjectManagement``: every query is scoped to the parent of
    the URL, new rows are attached to it, and reaching it needs the view
    permissions of the parent model too.
    """

    type = 'inline_object_management'
    label = gettext_lazy('Inline CRUD table (children of the page parent)')
    icon = 'fa fa-sitemap'
    props_schema = {
        **ObjectManagementComponent.props_schema,
        'required': ['model', 'form', 'parent_field'],
        'properties': {
            **ObjectManagementComponent.props_schema['properties'],
            'parent_field': {'type': 'string', 'x-widget': 'model-field',
                             'x-filter': 'parent-fk',
                             'title': 'Foreign key to the page parent'},
        },
    }

    def resolve(self, node, rctx, path):
        props = node.get('props') or {}
        parent = (rctx.design.get('meta') or {}).get('parent')
        if not parent:
            rctx.error(path, _('an inline table needs a page with a parent '
                               '(meta.parent)'))
            return data_build(ObjectManagementBuild, node, rctx)
        parent_found = rctx.exposure(parent.get('model'), path)
        found = rctx.exposure(props['model'], path + '.props.model')
        if parent_found is None or found is None:
            return data_build(ObjectManagementBuild, node, rctx)
        parent_field = props['parent_field']
        model_field = allowed_fields(found).get(parent_field)
        if model_field is None or kind_of(model_field) not in SINGLE_RELATIONS \
                or model_field.related_model is not parent_found.model:
            rctx.error(path + '.props.parent_field',
                       _('%(field)r is not a foreign key of %(model)s to '
                         '%(parent)s') % {'field': parent_field,
                                          'model': props['model'],
                                          'parent': parent_found.label})
            return data_build(ObjectManagementBuild, node, rctx)
        form = rctx.form(props['form'], path + '.props.form')
        if form is not None and parent_field in form.field_names:
            rctx.error(path + '.props.form',
                       _('remove %r from the form: the parent comes from the URL')
                       % (parent_field,))
            return data_build(ObjectManagementBuild, node, rctx)
        return self.resolve_management(node, rctx, path, parent_field=parent_field,
                                       parent_model=parent_found.model,
                                       parent_perms=parent_found.permissions('view'))


# -- charts and stats ------------------------------------------------------------------

def source_columns(source, rctx, path):
    """``{name: Column}`` of a data source, or None when they cannot be read
    without a request (they are checked when serving then)."""
    try:
        return source.column_map(rctx.request)
    except Exception:  # noqa: BLE001 -- a function source may need a request
        return None


def view_perms(rctx, props, path, default):
    perms = props.get('perms') or default
    if not perms:
        rctx.error(path + '.props.perms', _('say which permissions can see it: '
                                            'neither the data source nor the page '
                                            'has any'))
        return []
    check_permissions(rctx, path + '.props.perms', perms)
    return list(perms)


def resolve_measure(build, rctx, props, path):
    """Model or data source, aggregate and value field of a chart or stat.

    Returns ``({name: kind}, {name: model field})`` of the columns it may
    name -- the kinds are None when a data source cannot tell them without a
    request, the fields empty for a data source -- or ``(None, None)`` after
    an error.
    """
    has_model, has_source = bool(props.get('model')), bool(props.get('datasource'))
    if has_model == has_source:
        rctx.error(path + '.props', _('give a "model" or a "datasource", not both'))
        return None, None
    aggregate = props.get('aggregate', 'count')
    value_field = props.get('value_field')
    if has_source:
        by_name = {}
        source = rctx.datasource(props['datasource'], path + '.props.datasource')
        if source is None:
            return None, None
        columns = source_columns(source, rctx, path)
        kinds = None if columns is None else {
            name: column.kind for name, column in columns.items()}
        aggregatable = None if columns is None else {
            name for name, column in columns.items() if column.aggregatable}
        source_perms = list(source.perms) if isinstance(source.perms, (list, tuple)) \
            else []
        build.datasource = props['datasource']
        build.perms = view_perms(rctx, props, path, source_perms
                                 or format.view_permissions(rctx.design))
        title = str(source.get_label())
    else:
        found = rctx.exposure(props['model'], path + '.props.model')
        if found is None:
            return None, None
        by_name = allowed_fields(found)
        kinds = {name: kind_of(model_field) for name, model_field in by_name.items()
                 if not model_field.primary_key}
        aggregatable = {name for name, kind in kinds.items() if kind in NUMBER_KINDS}
        build.model = found.model
        build.columns = columns_of(found)
        build.perms = view_perms(rctx, props, path, found.permissions('view'))
        for name in kinds:
            if by_name[name].is_relation and not by_name[name].many_to_many:
                kinds[name] = 'relation'
        title = plural(found.model)
    if aggregate != 'count' or value_field:
        if not value_field:
            rctx.error(path + '.props.value_field', _('%s needs a value_field')
                       % aggregate)
        elif aggregatable is not None and value_field not in aggregatable:
            rctx.error(path + '.props.value_field',
                       _('%(aggregate)s needs a numeric value_field; %(field)r '
                         'is not one') % {'aggregate': aggregate,
                                          'field': value_field})
    build.aggregate = aggregate
    build.value_field = value_field
    build.title = props.get('title') or title
    return kinds, by_name


class ChartComponent(RuntimeComponent):
    """A Chart.js chart (``DJGraph``) of one aggregate grouped by a column.

    ``group_by`` a field, or a date field and a ``period``; ``aggregate`` one
    of count, sum, avg, min, max of ``value_field``. Over a ``model`` (exposed)
    or a ``datasource`` of djgentelella.datasources.
    """

    type = 'chart'
    label = gettext_lazy('Chart')
    icon = 'fa fa-bar-chart'
    default_props = {'chart': 'bar', 'aggregate': 'count'}
    props_schema = {
        'type': 'object',
        'required': ['group_by'],
        'additionalProperties': False,
        'properties': {
            'model': {'type': 'string', 'x-widget': 'model', 'title': 'Model'},
            'datasource': {'type': 'string', 'x-widget': 'datasource',
                           'title': 'Data source (instead of a model)'},
            'title': {'type': 'string', 'title': 'Title'},
            'chart': {'enum': list(CHART_TYPES), 'title': 'Chart'},
            'group_by': {'type': 'string', 'x-widget': 'model-field',
                         'x-filter': 'groupable', 'title': 'Group by'},
            'period': {'enum': list(PERIODS),
                       'title': 'Period (when grouping by a date)'},
            'aggregate': {'enum': list(AGGREGATES), 'title': 'Aggregate'},
            'value_field': {'type': 'string', 'x-widget': 'model-field',
                            'x-filter': 'numeric',
                            'title': 'Value (for sum, avg, min, max)'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100,
                      'title': 'At most this many groups (default 10)'},
            'perms': {**PERMISSION_LIST, 'x-widget': 'perms',
                      'title': 'Permissions to see it (empty = the model view)'},
        },
    }

    def resolve(self, node, rctx, path):
        props = node.get('props') or {}
        build = data_build(ChartBuild, node, rctx, chart=props.get('chart', 'bar'),
                           limit=props.get('limit', 10))
        kinds, fields = resolve_measure(build, rctx, props, path)
        if fields is None:
            return build
        group = props['group_by']
        kind = kinds.get(group) if kinds is not None else None
        if kinds is not None and (kind is None or kind in (
                'm2m', 'auto', 'file', 'image', 'json', 'binary', 'text')):
            rctx.error(path + '.props.group_by',
                       _('%r cannot be grouped by') % (group,))
            return build
        if kind == 'relation':
            check_relation(rctx, path + '.props.group_by', fields[group])
        period = props.get('period')
        if kind in DATE_KINDS:
            period = period or 'month'
        elif period and kinds is not None:
            rctx.error(path + '.props.period', _('a period needs a date group_by'))
        build.group_by = group
        build.period = period
        if not props.get('title') and build.model is not None and kind is not None:
            build.title = '%s by %s' % (plural(build.model),
                                        str(fields[group].verbose_name))
        return build

    def render(self, build, rctx, children):
        if not build.group_by:
            return mark_safe('')
        context = {'b': build, 'preview': rctx.preview}
        if rctx.preview:
            rows = factories.chart_rows(build, rctx.request)
            context['sample'] = json_config(build.id + '_gtsample', {
                'type': {'horizontal_bar': 'bar'}.get(build.chart, build.chart),
                'labels': [row['label'] for row in rows],
                'values': [row['value'] for row in rows],
                'horizontal': build.chart == 'horizontal_bar'})
        elif not can(rctx, build.perms):
            return no_permission(build)
        else:
            context['url'] = endpoint_url(rctx, build)
        return render_to_string('gtdesigns/components/chart.html', context)

    def media(self, build, rctx):
        return {'js': [SCRIPT]}

    def endpoints(self, build):
        if not build.group_by:
            return []
        return [Endpoint('', factories.chart_getter_for(build),
                         'gtdesign-%s' % build.id)]


class StatComponent(RuntimeComponent):
    """A tile with one number: an aggregate of a model or a data source.

    ``compare`` (``{"field": <date>, "period": "month"}``) shows the current
    period's value against the previous period's.
    """

    type = 'stat'
    label = gettext_lazy('Stat tile')
    icon = 'fa fa-tachometer'
    default_props = {'aggregate': 'count', 'icon': 'fa fa-cubes'}
    props_schema = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'model': {'type': 'string', 'x-widget': 'model', 'title': 'Model'},
            'datasource': {'type': 'string', 'x-widget': 'datasource',
                           'title': 'Data source (instead of a model)'},
            'title': {'type': 'string', 'title': 'Title'},
            'subtitle': {'type': 'string', 'title': 'Subtitle'},
            'icon': {'type': 'string', 'pattern': r'^[\w -]*$',
                     'title': 'Icon (CSS class)'},
            'aggregate': {'enum': list(AGGREGATES), 'title': 'Aggregate'},
            'value_field': {'type': 'string', 'x-widget': 'model-field',
                            'x-filter': 'numeric',
                            'title': 'Value (for sum, avg, min, max)'},
            'compare': {
                'type': 'object',
                'required': ['field'],
                'additionalProperties': False,
                'title': 'Compare with the previous period',
                'properties': {'field': {'type': 'string', 'x-widget': 'model-field',
                                         'x-filter': 'date'},
                               'period': {'enum': list(PERIODS)}},
            },
            'perms': {**PERMISSION_LIST, 'x-widget': 'perms',
                      'title': 'Permissions to see it (empty = the model view)'},
        },
    }

    def resolve(self, node, rctx, path):
        props = node.get('props') or {}
        build = data_build(StatBuild, node, rctx, subtitle=props.get('subtitle', ''),
                           icon=props.get('icon') or 'fa fa-cubes')
        kinds, fields = resolve_measure(build, rctx, props, path)
        compare = props.get('compare')
        if fields is not None and compare:
            if kinds and kinds.get(compare['field']) not in DATE_KINDS:
                rctx.error(path + '.props.compare.field',
                           _('%r is not a date') % (compare['field'],))
            build.compare_field = compare['field']
            build.period = compare.get('period', 'month')
        return build

    def render(self, build, rctx, children):
        if build.model is None and not build.datasource:
            return mark_safe('')
        context = {'b': build, 'preview': rctx.preview}
        if not rctx.preview and not can(rctx, build.perms):
            return no_permission(build)
        try:
            context['stat'] = factories.stat_value(build, rctx.request)
        except (APIException, PermissionDenied):
            # A data source that says no, or a value it cannot compute: the
            # tile shows nothing instead of taking the page down.
            context['stat'] = {'value': None, 'previous': None, 'change': None}
        if not rctx.preview:
            context['url'] = endpoint_url(rctx, build)
        return render_to_string('gtdesigns/components/stat.html', context)

    def endpoints(self, build):
        if build.model is None and not build.datasource:
            return []
        return [Endpoint('', factories.stat_view_for(build), 'gtdesign-%s' % build.id)]


# -- the classic CRUD ------------------------------------------------------------------

class CrudClassicComponent(RuntimeComponent):
    """djgentelella's classic, server rendered CRUD (``CRUDView``).

    Its pages -- list, create, detail, update, delete -- are served by the
    design router under the node's endpoint. In the page, ``mode: "embed"``
    (the default) shows the list itself, with its search and pagination;
    ``"link"`` a tile that opens it.
    """

    type = 'crud_classic'
    label = gettext_lazy('Classic CRUD (separate pages)')
    icon = 'fa fa-list-alt'
    props_schema = {
        'type': 'object',
        'required': ['model'],
        'additionalProperties': False,
        'properties': {
            'model': {'type': 'string', 'x-widget': 'model', 'title': 'Model'},
            'title': {'type': 'string', 'title': 'Title'},
            'form': {'type': 'string', 'x-widget': 'form',
                     'title': 'Form (empty: every field the model exposes)'},
            'list_fields': {'type': 'array', 'items': {'type': 'string'},
                            'x-widget': 'model-fields', 'title': 'List columns'},
            'search_fields': {'type': 'array', 'items': {'type': 'string'},
                              'x-widget': 'model-text-fields',
                              'title': 'Searched by the list search box'},
            'views': {'type': 'array', 'items': {'enum': list(CRUD_VIEWS)},
                      'title': 'Pages (default: all of %s)' % ', '.join(CRUD_VIEWS)},
            'perms': {
                'type': 'object',
                'x-widget': 'perms',
                'title': 'Permissions per page (empty = the model ones)',
                'additionalProperties': False,
                'properties': {view: PERMISSION_LIST for view in CRUD_VIEWS},
            },
            'mode': {'enum': ['embed', 'link'],
                     'title': 'The list in the page, or a link to it'},
            'column_conditions': conditions_schema(
                'Columns shown only when (by field)'),
            'action_conditions': conditions_schema(
                'Pages allowed only when',
                [view for view in CRUD_VIEWS if view != 'list']),
            'paginate_by': {'type': 'integer', 'minimum': 1, 'maximum': 200},
        },
    }

    def resolve(self, node, rctx, path):
        props = node.get('props') or {}
        build = data_build(CrudBuild, node, rctx, mode=props.get('mode', 'embed'),
                           paginate_by=props.get('paginate_by', 10))
        found = rctx.exposure(props['model'], path + '.props.model')
        if found is None:
            return build
        model = found.model
        if props.get('form'):
            form = rctx.form(props['form'], path + '.props.form')
            if form is not None and form.model is not model:
                rctx.error(path + '.props.form', form_mismatch(props, form))
                return build
        else:
            errors_before = len(rctx.errors)
            form = build_form('%s_crud' % node['id'], {'model': props['model']}, rctx,
                              path + '.props.model')
            if len(rctx.errors) > errors_before:
                rctx.error(path + '.props.form', _('the default form (every field '
                                                   'the model exposes) does not '
                                                   'work: give a "form"'))
        if form is None:
            return build
        by_name = allowed_fields(found)
        list_fields = props.get('list_fields') or [
            name for name in form.field_names
            if kind_of(by_name[name]) not in ('m2m', 'text', 'json', 'file',
                                              'image')][:6]
        for name in list_fields:
            if name not in by_name:
                rctx.error(path + '.props.list_fields',
                           no_field(props['model'], name))
            else:
                check_relation(rctx, path + '.props.list_fields', by_name[name])
        search = props.get('search_fields')
        if search is None:
            search = [name for name in list_fields if name in by_name
                      and kind_of(by_name[name]) in TEXT_KINDS]
        for name in search:
            if name not in by_name or kind_of(by_name[name]) not in TEXT_KINDS:
                rctx.error(path + '.props.search_fields',
                           _('%(field)r is not a text field of %(model)s') % {
                               'field': name, 'model': props['model']})
        perms = {view: found.permissions(permission)
                 for view, permission in CRUD_PERMISSIONS.items()}
        perms.update(props.get('perms', {}))
        for view, needed in perms.items():
            check_permissions(rctx, path + '.props.perms.' + view, needed)
        detail_fields = list(dict.fromkeys(list(list_fields) + form.field_names))
        column_conditions = check_conditions(
            rctx, path + '.props.column_conditions', props.get('column_conditions'),
            detail_fields, _('column'))
        action_conditions = check_conditions(
            rctx, path + '.props.action_conditions', props.get('action_conditions'),
            [view for view in CRUD_VIEWS if view != 'list'], _('page'))
        if rctx.has_errors_under(path):
            return build
        build.title = props.get('title') or plural(model)
        build.model = model
        build.form = form
        build.list_fields = list(list_fields)
        build.search_fields = list(search)
        build.detail_fields = detail_fields
        build.views = list(props.get('views') or CRUD_VIEWS)
        build.perms = perms
        build.columns = columns_of(found)
        build.column_conditions = column_conditions
        build.action_conditions = action_conditions
        return build

    def render(self, build, rctx, children):
        if build.model is None:
            return mark_safe('')
        context = {'b': build, 'preview': rctx.preview}
        if rctx.preview:
            context['columns'] = [label(build.model._meta.get_field(name).verbose_name)
                                  for name in build.list_fields]
            context['rows'] = sample_rows(build.model, build.list_fields)
            return render_to_string('gtdesigns/components/crud_classic.html', context)
        if 'list' not in build.views or not can(rctx, build.perms['list']):
            return no_permission(build)
        base = endpoint_url(rctx, build)
        context['url'] = base
        if build.mode == 'embed' and base is not None:
            request = rctx.request
            request.gtdesign_embed = True
            request.gtdesign_crud_base = base
            try:
                response = factories.crud_view_for(build).list(request)
                response.render()
                context['embedded'] = mark_safe(response.content.decode())
            finally:
                request.gtdesign_embed = False
        return render_to_string('gtdesigns/components/crud_classic.html', context,
                                request=rctx.request)

    def endpoints(self, build):
        if build.model is None:
            return []
        return [Endpoint('', factories.crud_viewset_for(build),
                         'gtdesign-%s' % build.id)]


# -- facets -------------------------------------------------------------------

def target_hidden(rctx, build):
    """The columns the table a facets panel filters hides for the request
    (its ``column_conditions``)."""
    resolved = rctx.resolved or getattr(rctx.request, 'gtdesign_resolved', None)
    target = resolved.nodes.get(build.target) if resolved is not None else None
    if target is None or not getattr(target.build, 'column_conditions', None):
        return set()
    return hidden_columns(target.build, rctx.request,
                          condition_object(rctx, target.build))


def find_node(document, node_id):
    for node, _parent, _path in format.walk(document['root']):
        if node.get('id') == node_id:
            return node
    return None


class FacetsComponent(RuntimeComponent):
    """A facets panel (djgentelella.datasources' ``GTFacets``) bound to a
    table of the page by ``target``, its node id.

    Each count applies the other facets and the table's search; each change
    reloads the table with the facets as filters of the parameter document.
    """

    type = 'facets'
    label = gettext_lazy('Facets')
    icon = 'fa fa-filter'
    props_schema = {
        'type': 'object',
        'required': ['target', 'columns'],
        'additionalProperties': False,
        'properties': {
            'target': {'type': 'string', 'x-widget': 'node',
                       'x-filter': 'table', 'title': 'Table it filters'},
            'columns': {'type': 'array', 'items': {'type': 'string'},
                        'minItems': 1, 'x-widget': 'model-fields',
                        'title': 'Columns with a facet'},
            'title': {'type': 'string', 'title': 'Title'},
            'perms': {**PERMISSION_LIST, 'x-widget': 'perms',
                      'title': 'Permissions to see it (empty = the model view)'},
        },
    }

    def target_types(self, rctx):
        """The types of node a panel may filter: the tables, and those of the
        components that declare ``facets_target``."""
        components = rctx.components
        if components is None:
            # The registry imports this module.
            from djgentelella.designs import registry  # noqa: PLC0415 (circular)
            components = registry.get_components()
        return list(TABLE_TYPES) + sorted(
            node_type for node_type, component in components.items()
            if node_type not in TABLE_TYPES
            and getattr(component, 'facets_target', False))

    def resolve(self, node, rctx, path):
        props = node.get('props') or {}
        build = data_build(FacetsBuild, node, rctx, target=props['target'])
        target = find_node(rctx.design, props['target'])
        if target is not None and target.get('type') not in TABLE_TYPES:
            component = rctx.component(target.get('type'))
            if component is not None and getattr(component, 'facets_target', False):
                return self.resolve_source(node, rctx, path, build, component, target)
        if target is None or target.get('type') not in TABLE_TYPES:
            rctx.error(path + '.props.target',
                       _('%(target)r is not the id of a table (%(types)s) of this '
                         'page') % {'target': props['target'],
                                    'types': ', '.join(self.target_types(rctx))})
            return build
        found = rctx.exposure((target.get('props') or {}).get('model'),
                              path + '.props.target')
        if found is None:
            return build
        by_name = allowed_fields(found)
        for name in props['columns']:
            model_field = by_name.get(name)
            if model_field is None or model_field.primary_key or kind_of(
                    model_field) in ('json', 'file', 'image', 'binary', 'point'):
                rctx.error(path + '.props.columns',
                           _('%r cannot have a facet') % (name,))
            else:
                check_relation(rctx, path + '.props.columns', model_field)
        build.perms = view_perms(rctx, props, path, found.permissions('view'))
        if rctx.has_errors_under(path):
            return build
        build.title = props.get('title') or _('Filters')
        build.model = found.model
        build.columns = list(props['columns'])
        build.inline = target['type'] == 'inline_object_management'
        return build

    def resolve_source(self, node, rctx, path, build, component, target):
        """A panel over a node of another component: over the data source
        its ``facets_source()`` names, through the data source API."""
        props = node.get('props') or {}
        name = component.facets_source(target, rctx, path + '.props.target')
        if not name:
            if not rctx.has_errors_under(path):
                rctx.error(path + '.props.target', _('node %r has no data source to '
                                                     'filter') % (props['target'],))
            return build
        source = rctx.datasource(name, path + '.props.target')
        if source is None:
            return build
        columns = source_columns(source, rctx, path)
        if columns is not None:
            for column_name in props['columns']:
                column = columns.get(column_name)
                if column is None or not column.filterable or column.kind == 'json':
                    rctx.error(path + '.props.columns',
                               _('%r cannot have a facet') % (column_name,))
        if props.get('perms'):
            build.perms = view_perms(rctx, props, path, [])
        if rctx.has_errors_under(path):
            return build
        build.datasource = source.name
        build.title = props.get('title') or _('Filters')
        build.columns = list(props['columns'])
        return build

    def render(self, build, rctx, children):
        if build.datasource:
            return self.render_source(build, rctx)
        if build.model is None:
            return mark_safe('')
        context = {'b': build, 'preview': rctx.preview}
        if rctx.preview:
            context['facets'] = [
                (label(build.model._meta.get_field(name).verbose_name),
                 ['%s 1' % _('Value'), '%s 2' % _('Value')]) for name in build.columns]
            return render_to_string('gtdesigns/components/facets.html', context)
        if not can(rctx, build.perms):
            return no_permission(build)
        # A facet of a column its table hides (column_conditions) would
        # count what the table does not show.
        hidden = target_hidden(rctx, build)
        if hidden:
            context['b'] = copy.copy(build)
            context['b'].columns = [name for name in build.columns
                                    if name not in hidden]
            if not context['b'].columns:
                return mark_safe('')
        if build.inline:
            parent = getattr(rctx.request, 'gtdesign_parent', None)
            url = endpoint_url(rctx, build, parent.pk) if parent is not None else None
        else:
            url = endpoint_url(rctx, build)
        if url is None:
            return no_permission(build)
        context.update(url=url, group='gtdesign:%s' % build.target,
                       columns=','.join(context['b'].columns))
        return render_to_string('gtdesigns/components/facets.html', context)

    def render_source(self, build, rctx):
        context = {'b': build, 'preview': rctx.preview}
        if rctx.preview:
            context['facets'] = [(name, ['%s 1' % _('Value'), '%s 2' % _('Value')])
                                 for name in build.columns]
            return render_to_string('gtdesigns/components/facets.html', context)
        if build.perms and not can(rctx, build.perms):
            return no_permission(build)
        try:
            source = get_datasource(build.datasource)
            url = reverse('gtdatasource', kwargs={'name': build.datasource})
        except (KeyError, LookupError, NoReverseMatch):
            source = url = None
        if source is None or rctx.request is None or \
                not source.has_permission(rctx.request):
            return no_permission(build)
        context.update(url=url, group='gtdesign:%s' % build.target,
                       columns=','.join(build.columns))
        return render_to_string('gtdesigns/components/facets.html', context)

    def media(self, build, rctx):
        return {'js': [SCRIPT]}

    def depends_on(self, build):
        """The table it filters: hidden by a condition, it hides the panel
        and its endpoint too."""
        return [build.target] if build.target else []

    def endpoints(self, build):
        if build.model is None or build.datasource:
            # A data source target is served by the data source API, with
            # the source's own permissions.
            return []
        suffix = r'(?P<parent_pk>[^/.]+)' if build.inline else ''
        return [Endpoint(suffix, factories.facets_viewset_for(build),
                         'gtdesign-%s' % build.id)]


DATA_COMPONENTS = [ObjectManagementComponent, InlineObjectManagementComponent,
                   ChartComponent, StatComponent, CrudClassicComponent,
                   FacetsComponent]
