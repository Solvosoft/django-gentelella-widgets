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

import contextlib
import contextvars
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
from djgentelella.designs import conditions, factories, format, pipeline, source_tables
from djgentelella.designs.builds import (
    ACTION_PERMISSIONS, AGGREGATES, CHART_TYPES, CRUD_PERMISSIONS, CRUD_VIEWS,
    PERIODS, TABLE_ACTIONS, ChartBuild, CrudBuild, FacetsBuild, ObjectManagementBuild,
    RowLink, StatBuild,
)
from djgentelella.designs.components import Endpoint, RuntimeComponent
from djgentelella.designs.conditions import (
    check_conditions, conditions_schema, denied, hidden_columns,
)
from djgentelella.designs.forms import build_form, is_form_field, no_field
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
           'StatComponent', 'parse_flow_link', 'resolve_row_link',
           'FACETS_TEMPLATE', 'facets_page_context', 'TABLE_TEMPLATE',
           'links_to_itself', 'master_detail_config', 'master_detail_of',
           'publishing_path',
           'row_link_config', 'table_page_context', 'can', 'data_build']

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
    """The hash of the document being resolved: only the key the factories
    cache their classes by (with the node id), never an identity to check.

    A build written as code (djgentelella-editor) may set any stable string
    -- ``'<app>.<slug>'`` --: two builds of the same node with different
    content must just not share it within one process.
    """
    if '_gtdesign_hash' not in rctx.__dict__:
        rctx._gtdesign_hash = format.document_hash(rctx.design)
    return rctx._gtdesign_hash


def data_build(build_class, node, rctx, **kwargs):
    """The ``build_class`` (a :class:`~djgentelella.designs.components.Build`)
    of the document ``node``: its id, type and a copy of its props, with the
    page hash the factories cache their classes by and the preview flag of
    ``rctx``; ``kwargs`` are the build's own fields."""
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


SITE_FIELD_SCHEMA = {
    'type': 'string', 'x-widget': 'model-field', 'x-filter': 'site',
    'title': 'Foreign key to the Site (only the rows of the current Site and '
             'the global ones; set on creation)'}


def resolve_site_field(rctx, path, model, props, form=None):
    """The ``site_field`` of ``props``: a foreign key of ``model`` to
    ``sites.Site`` that ``form`` (a :class:`~djgentelella.designs.forms.
    FormBuild`) does not ask for -- the component sets it --, or ``''``."""
    site_field = props.get('site_field') or ''
    if not site_field:
        return ''
    model_field = next((item for item in model._meta.get_fields()
                        if item.name == site_field), None)
    related = getattr(model_field, 'related_model', None)
    if model_field is None or not model_field.many_to_one or \
            related is None or related._meta.label_lower != 'sites.site':
        rctx.error(path + '.props.site_field',
                   _('%(field)r is not a foreign key of %(model)s to sites.Site')
                   % {'field': site_field, 'model': model._meta.label})
    elif form is not None and site_field in form.field_names:
        rctx.error(path + '.props.site_field',
                   _('%r is the site_field: the component sets it, the form '
                     'cannot ask for it') % (site_field,))
    return site_field


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
    """Whether the user of ``rctx`` has every permission of ``perms``
    (``app.codename``); ``False`` without a user (publishing, a command)."""
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


#: The prop that makes the version mandatory (C9): with it, saving without
#: the version that was read is refused (428 in the API, a form error in the
#: classic CRUD) instead of saving as before. It turns ``optimistic_lock`` on.
OPTIMISTIC_LOCK_REQUIRED_SCHEMA = {
    'type': 'boolean', 'default': False,
    'title': 'Refuse to save without the version that was read (turns '
             'optimistic locking on)'}


def lock_props_errors(props, path):
    """The error of ``optimistic_lock_required`` with ``optimistic_lock``
    turned off on purpose (``false``)."""
    if props.get('optimistic_lock_required') is True and \
            props.get('optimistic_lock') is False:
        return [format.Error(path + '.props.optimistic_lock_required', _(
            'optimistic_lock_required needs optimistic_lock'))]
    return []


def lock_props(props, lock_default=False):
    """``(optimistic_lock, optimistic_lock_required)`` of valid props:
    requiring the version turns locking on."""
    required = bool(props.get('optimistic_lock_required', False))
    return bool(props.get('optimistic_lock', lock_default)) or required, required


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


#: The path a document is being published at (:func:`publishing_path`).
_PUBLISHING_PATH = contextvars.ContextVar('gtdesign_publishing_path', default=None)


@contextlib.contextmanager
def publishing_path(path):
    """While a document is validated to be published at ``path``, a row link
    ``page:<path>`` names that page itself (:func:`links_to_itself`), even
    when the path is not the document's ``meta.url``.
    :func:`~djgentelella.designs.publishing.publish` sets it."""
    token = _PUBLISHING_PATH.set(normalize_path(path) if path else None)
    try:
        yield
    finally:
        _PUBLISHING_PATH.reset(token)


def links_to_itself(document, name, path=None):
    """Whether the row link ``name`` names the page of ``document`` itself:
    ``page:<its meta.url>``, ``page:<path>`` (the path it is published at:
    ``path``, else the one of :func:`publishing_path`) or its
    ``meta.url_name``."""
    meta = (document or {}).get('meta') or {}
    if name.startswith(PAGE_PREFIX):
        target = normalize_path(name[len(PAGE_PREFIX):])
        path = path or _PUBLISHING_PATH.get()
        if path and target == normalize_path(path):
            return True
        return bool(meta.get('url')) and target == normalize_path(meta['url'])
    return bool(meta.get('url_name')) and name == meta['url_name']


#: The key of a node ``meta`` that declares a master-detail
#: (djgentelella-editor's ``gteditor.components.master_detail``).
MASTER_DETAIL_KEY = 'master_detail'


def master_detail_of(document, node_id):
    """The ``meta.master_detail`` (a dict) of the node of ``document`` that
    names the table ``node_id`` as its ``master``, or ``None``.

    A master-detail is a ``row`` whose ``meta.master_detail`` is ``{"variant":
    ..., "master": "<id of an object_management>"}``: a page about one master
    (``meta.parent``) lists the masters in that table and the details of the
    one chosen. The engine only reads it to mark the current master and to
    choose one with a click (:func:`master_detail_config`); the layout is the
    row's.
    """
    pending = [(document or {}).get('root')]
    while pending:
        node = pending.pop()
        if not isinstance(node, dict):
            continue
        meta = node.get('meta')
        found = meta.get(MASTER_DETAIL_KEY) if isinstance(meta, dict) else None
        if isinstance(found, dict) and found.get('master') == node_id:
            return found
        children = node.get('children')
        if isinstance(children, list):
            pending.extend(reversed(children))
    return None


def master_detail_config(build, rctx):
    """What the master table ``build`` of a master-detail page needs in the
    browser, or ``None`` when it is not one: ``{"current": pk of the master of
    the page or None, "url": the page of a master, "placeholder": the pk in
    "url", "variant"}``.

    Only for a table over the model of the page's ``meta.parent`` on a page
    with a ``meta.url``: a click on a row opens the page of that master
    (``url`` with the row's pk in place of ``placeholder``).
    """
    found = master_detail_of(rctx.design, build.id)
    if found is None or build.model is None or build.inline:
        return None
    meta = (rctx.design or {}).get('meta') or {}
    parent = (meta.get('parent') or {}).get('model')
    if not isinstance(parent, str) or parent.lower() != build.model._meta.label_lower \
            or not meta.get('url'):
        return None
    placeholder = PK_PLACEHOLDERS[0]
    try:
        url = reverse('gt-design-page', args=['%s/%s' % (
            normalize_path(meta['url']), placeholder)])
    except NoReverseMatch:
        return None
    current = getattr(rctx.request, 'gtdesign_parent', None)
    return {'current': (str(current.pk) if isinstance(current, build.model)
                        else None),
            'url': url, 'placeholder': placeholder,
            'variant': str(found.get('variant') or '')}


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
    djgentelella-editor names the flows it designs (``<app>.<slug>``).

    The context's hook answers
    (:meth:`~djgentelella.designs.components.ResolveContext.flow`): a
    subclass of the context changes it.
    """
    return rctx.flow(name)


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
    if page is None and links_to_itself(rctx.design, name):
        # The page being published, not saved yet (a master-detail page
        # whose rows link to itself): its own meta.parent decides.
        page = Page(path=normalize_path(_PUBLISHING_PATH.get()
                                        or rctx.design['meta']['url']),
                    document=rctx.design)
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
    markdown = set(factories.markdown_fields(build))
    for name in build.list_fields:
        if name in hidden:
            continue
        model_field = build.model._meta.get_field(name)
        kind = kind_of(model_field)
        lookup = build.lookups.get(name)
        column = {'data': name, 'name': name, 'kind': kind,
                  'title': escape(source_tables.column_title(
                      build, name, label(model_field.verbose_name))),
                  'type': column_type(describe_field(model_field), bool(lookup))}
        if kind == 'choices':
            column['choices'] = [[value, escape(str(text))]
                                 for value, text in model_field.flatchoices]
        if kind == 'm2m' and lookup:
            column['multiple'] = True
        if name in markdown:
            # Its row carries <name>_html, cleaned on the server.
            column['markdown'] = True
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


TABLE_TEMPLATE = 'gtdesigns/components/object_management.html'


def list_page_context(build, request, url, user):
    if not url or request is None:
        return None
    if build.perms['list'] and (user is None or
                                not all_permission(user, list(build.perms['list']))):
        return None
    try:
        source = get_datasource(build.datasource)
    except (KeyError, LookupError):
        source = None
    if source is None or not source.has_permission(request):
        return None
    hidden = hidden_columns(build, request)
    columns = []
    for column in source_tables.visible_columns(build, hidden):
        item = {'data': column['name'], 'name': column['name'],
                'kind': column['kind'], 'title': escape(column['title']),
                'type': 'string' if column['kind'] in TEXT_KINDS else 'readonly'}
        if 'choices' in column:
            item['choices'] = [[value, escape(text)]
                               for value, text in column['choices']]
        columns.append(item)
    config = {
        'id': build.id,
        'readonly': True,
        'urls': {'list_url': url},
        'modal_ids': {},
        'columns': columns,
        'row_links': row_link_config(build, request),
        'delete_display': '',
    }
    return {'b': build, 'template': TABLE_TEMPLATE, 'forms': {}, 'base': url,
            'modal_ids': {}, 'allowed': {},
            'config': json_config(build.id + '_gtconfig', config)}


def table_page_context(build, request, url):
    """What :data:`TABLE_TEMPLATE` needs to draw ``object_management`` in
    list mode (``build.list_only``: over a ``datasource``, without a form)
    for ``request``: ``{'b', 'template', 'forms', 'base', 'modal_ids',
    'allowed', 'config'}``, with ``url`` the URL of its endpoint -- a
    :class:`~djgentelella.designs.source_tables.SourceTableViewSet` serving
    ``build`` -- and ``config`` the DataTable's ``data-gtconfig`` (columns
    the request sees, row links). Render it with ``request=request``.

    No published :class:`~djgentelella.designs.models.Page` is needed, as
    :func:`~djgentelella.designs.grid.grid_page_context`. ``None`` when the
    request may not see the list: without ``perms["list"]``, without the
    data source or its ``has_permission``, or without ``url``. A table with
    a form (CRUD) is not in list mode: ``ValueError``.
    """
    if not build.list_only:
        raise ValueError('%r is not a list over a data source' % (build.id,))
    return list_page_context(build, request, url, getattr(request, 'user', None))


class ObjectManagementComponent(RuntimeComponent):
    """A DataTable of a model with create, update, detail and delete modals.

    The djgentelella "object management" pattern: an
    ``AuthAllPermBaseObjectManagement`` viewset (permission checked per
    action), its serializers and FilterSet -- all made at runtime -- and
    ``ObjectCRUD`` in the page.

    In list mode -- a ``datasource`` instead of ``model`` and ``form`` -- it
    only lists the rows of any data source, read only
    (:mod:`djgentelella.designs.source_tables`).
    """

    type = 'object_management'
    label = gettext_lazy('Object management (CRUD table)')
    icon = 'fa fa-table'
    props_schema = {
        'type': 'object',
        # "model" and "form", or "datasource": checked by resolve().
        'additionalProperties': False,
        'properties': {
            'model': {'type': 'string', 'x-widget': 'model', 'title': 'Model'},
            'datasource': {'type': 'string', 'x-widget': 'datasource',
                           'title': 'Data source (instead of a model and a form): '
                                    'its rows listed, read only'},
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
            'optimistic_lock': {
                'type': 'boolean', 'default': False,
                'title': 'Refuse to save a row somebody else changed '
                         'after it was opened (optimistic locking)'},
            'optimistic_lock_required': OPTIMISTIC_LOCK_REQUIRED_SCHEMA,
            'column_labels': source_tables.COLUMN_LABELS_SCHEMA,
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
            'pipeline': pipeline.PIPELINE_SCHEMA,
            'site_field': SITE_FIELD_SCHEMA,
        },
    }

    def resolve(self, node, rctx, path):
        props = node.get('props') or {}
        if props.get('datasource'):
            return self.resolve_list(node, rctx, path)
        missing = [name for name in ('model', 'form') if not props.get(name)]
        if missing:
            for name in missing:
                rctx.error(path + '.props.' + name,
                           _('%s is required (or a "datasource", to only list its '
                             'rows)') % name)
            return data_build(ObjectManagementBuild, node, rctx)
        return self.resolve_management(node, rctx, path)

    def resolve_list(self, node, rctx, path):
        """List mode: the rows of ``datasource``, read only."""
        props = node.get('props') or {}
        build = data_build(ObjectManagementBuild, node, rctx)
        for name in ('model', 'form', 'notify', 'action_conditions', 'pipeline',
                     'site_field'):
            if props.get(name):
                rctx.error(path + '.props.' + name,
                           _('a list over a data source only reads: it has no '
                             '%r') % (name,))
        if props.get('optimistic_lock') or props.get('optimistic_lock_required'):
            rctx.error(path + '.props.optimistic_lock',
                       _('a list over a data source only reads: there is nothing '
                         'to lock'))
        source = source_tables.resolve_source_list(
            rctx, path, props, build, names_prop='list_fields')
        if source is not None:
            links = props.get('row_links') or []
            if build.model is not None:
                build.row_links = resolve_row_links(rctx, path, build.model, links)
            elif links:
                rctx.error(path + '.props.row_links',
                           _('row links need a data source over a model'))
        if rctx.has_errors_under(path):
            # Nothing is served from a node with errors.
            build.model, build.datasource = None, ''
        return build

    def facets_source(self, node, rctx, path):
        """A facets panel filters a list over a data source through the data
        source API."""
        return (node.get('props') or {}).get('datasource') or None

    def resolve_management(self, node, rctx, path, parent_field=None,
                           parent_model=None, parent_perms=(), parent_site_field=''):
        props = node.get('props') or {}
        build = data_build(ObjectManagementBuild, node, rctx,
                           parent_field=parent_field, parent_model=parent_model,
                           parent_perms=list(parent_perms),
                           parent_site_field=parent_site_field or '')
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
        column_labels = source_tables.resolve_column_labels(
            rctx, path, props, list(list_names))
        notify = None
        if props.get('notify'):
            notify = resolve_notify(rctx, path, model, props['notify'])
        on_submit = pipeline.resolve_pipeline(
            rctx, props, path, event=pipeline.ON_SUBMIT, model=model,
            exposure=found, form_fields=form.field_names)
        site_field = ''
        if props.get('site_field'):
            # An inline table too: its rows are those of the parent and of the
            # request's Site (or global), and a new one gets the Site.
            site_field = resolve_site_field(rctx, path, model, props, form)
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
        build.column_labels = column_labels
        build.action_conditions = action_conditions
        build.optimistic_lock, build.optimistic_lock_required = lock_props(props)
        build.pipeline = on_submit
        build.site_field = site_field
        return build

    def check_props(self, node, path):
        errors = super().check_props(node, path)
        return errors or lock_props_errors(node.get('props') or {}, path)

    def base_url(self, build, rctx):
        if build.inline:
            parent = getattr(rctx.request, 'gtdesign_parent', None)
            if parent is None:
                return None
            return endpoint_url(rctx, build, parent.pk)
        return endpoint_url(rctx, build)

    def render_list(self, build, rctx):
        """List mode: a DataTable without modals over the node's endpoint."""
        if rctx.preview:
            return render_to_string('gtdesigns/components/object_management.html', {
                'b': build, 'preview': True,
                'columns': [column['title'] for column in build.source_columns],
                'rows': [['%s %d' % (column['title'], index)
                          for column in build.source_columns]
                         for index in range(1, 4)]})
        context = list_page_context(build, rctx.request, endpoint_url(rctx, build),
                                    rctx.user)
        if context is None:
            return no_permission(build)
        return render_to_string(TABLE_TEMPLATE, context, request=rctx.request)

    def render(self, build, rctx, children):
        if build.list_only:
            return self.render_list(build, rctx)
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
            forms['create'] = build.form.get_form(prefix=prefix + '_create',
                                                  request=rctx.request)
        if allowed['update']:
            modal_ids['update'] = '#%s_update_modal' % prefix
            forms['update'] = build.form.get_form(prefix=prefix + '_update',
                                                  request=rctx.request)
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
        master = master_detail_config(build, rctx)
        if master is not None:
            config['master'] = master
        return render_to_string('gtdesigns/components/object_management.html', {
            'b': build, 'forms': forms, 'base': base, 'modal_ids': modal_ids,
            'allowed': allowed,
            'config': json_config(build.id + '_gtconfig', config),
        }, request=rctx.request)

    def media(self, build, rctx):
        return {'js': [SCRIPT]}

    def endpoints(self, build):
        if build.list_only:
            return [Endpoint('', source_tables.SourceTableViewSet,
                             'gtdesign-%s' % build.id)]
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
            **{name: schema for name, schema in
               ObjectManagementComponent.props_schema['properties'].items()
               if name != 'datasource'},
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
                                       parent_perms=parent_found.permissions('view'),
                                       parent_site_field=parent_found.site_field)


# -- charts and stats ------------------------------------------------------------------

def source_columns(source, rctx, path):
    """``{name: Column}`` of a data source, or None when they cannot be read
    without a request (they are checked when serving then): for the request,
    or without one for the Site of ``rctx``
    (:meth:`~djgentelella.designs.components.ResolveContext.source_columns`)."""
    return rctx.source_columns(source)


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
            'facets': {'type': 'string', 'x-widget': 'node', 'x-filter': 'facets',
                       'title': 'Facets panel that filters it, as it filters '
                                'its table (empty = every row)'},
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
        if props.get('facets'):
            self.resolve_facets(build, rctx, path + '.props.facets',
                                props['facets'], kinds)
        return build

    def resolve_facets(self, build, rctx, where, facets_id, kinds):
        """Bind the chart to the ``facets`` panel ``facets_id``: the panel
        must filter the chart's rows -- a table over the chart's model, or
        a node whose data source (``facets_source``) is the chart's -- and
        its columns must be columns of the chart."""
        panel = find_node(rctx.design, facets_id)
        if panel is None or panel.get('type') != 'facets':
            rctx.error(where, _('%r is not the id of a facets panel of this page')
                       % (facets_id,))
            return
        panel_props = panel.get('props') or {}
        target = find_node(rctx.design, panel_props.get('target') or '')
        if target is None:
            return  # the panel reports its own target
        target_type = target.get('type')
        if build.datasource:
            component = rctx.component(target_type)
            name = None
            if target_type not in TABLE_TYPES and component is not None \
                    and getattr(component, 'facets_target', False):
                name = component.facets_source(target, rctx, where)
            if name != build.datasource:
                rctx.error(where, _('facets panel %(panel)r does not filter data '
                                    'source %(source)r, the one of the chart') % {
                    'panel': facets_id, 'source': build.datasource})
                return
        elif target_type == 'inline_object_management':
            rctx.error(where, _('facets panel %r filters the rows of one parent '
                                '(an inline table): a chart cannot follow it')
                       % (facets_id,))
            return
        else:
            found = rctx.exposure((target.get('props') or {}).get('model'))
            if target_type not in TABLE_TYPES or found is None \
                    or found.model is not build.model:
                rctx.error(where, _('facets panel %(panel)r does not filter rows '
                                    'of %(model)s, the model of the chart') % {
                    'panel': facets_id,
                    'model': build.model._meta.label if build.model else '-'})
                return
        columns = list(panel_props.get('columns') or [])
        for name in columns:
            if kinds is not None and name not in kinds:
                rctx.error(where, _('facet %r is not a column the chart can '
                                    'filter') % (name,))
        build.facets = facets_id
        build.facets_target = target['id']
        build.facet_columns = columns
        # The target's column_conditions travel with the build: a facet over
        # a column it hides is refused without looking at the page.
        conditions_of_target = (target.get('props') or {}).get('column_conditions')
        build.facet_conditions = dict(conditions_of_target) \
            if isinstance(conditions_of_target, dict) else {}

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
            # The chart follows the facets of its panel (data_components.js).
            context['facets_target'] = build.facets_target if build.facets else ''
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
            'optimistic_lock': {
                'type': 'boolean', 'default': False,
                'title': 'Refuse to save an object somebody else changed '
                         'after its update page was opened (optimistic locking)'},
            'optimistic_lock_required': OPTIMISTIC_LOCK_REQUIRED_SCHEMA,
            'pipeline': pipeline.PIPELINE_SCHEMA,
            'site_field': SITE_FIELD_SCHEMA,
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
            form_data = {'model': props['model']}
            if props.get('site_field'):
                # The default form leaves out the field the component sets.
                form_data['fields'] = [
                    model_field.name for model_field in found.model_fields()
                    if is_form_field(model_field)
                    and model_field.name != props['site_field']]
            form = build_form('%s_crud' % node['id'], form_data, rctx,
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
        on_submit = pipeline.resolve_pipeline(
            rctx, props, path, event=pipeline.ON_SUBMIT, model=model,
            exposure=found, form_fields=form.field_names)
        site_field = resolve_site_field(rctx, path, model, props, form)
        if rctx.has_errors_under(path):
            return build
        build.pipeline = on_submit
        build.site_field = site_field
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
        build.optimistic_lock, build.optimistic_lock_required = lock_props(props)
        return build

    def check_props(self, node, path):
        errors = super().check_props(node, path)
        return errors or lock_props_errors(node.get('props') or {}, path)

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


FACETS_TEMPLATE = 'gtdesigns/components/facets.html'


def source_facets_context(build, request, user, datasource_url=None):
    """The context of :data:`FACETS_TEMPLATE` for a panel over a data source,
    or ``None`` when ``user``/``request`` may not see it."""
    if build.perms and (user is None or not all_permission(user, list(build.perms))):
        return None
    try:
        source = get_datasource(build.datasource)
        url = datasource_url or reverse('gtdatasource',
                                        kwargs={'name': build.datasource})
    except (KeyError, LookupError, NoReverseMatch):
        source = url = None
    if source is None or request is None or not source.has_permission(request):
        return None
    return {'b': build, 'preview': False, 'template': FACETS_TEMPLATE, 'url': url,
            'group': 'gtdesign:%s' % build.target, 'columns': ','.join(build.columns)}


def facets_page_context(build, request, datasource_url=None, *, url=None,
                        target=None):
    """What :data:`FACETS_TEMPLATE` needs to draw the facets panel ``build``
    -- one over a data source: its target is a component over a
    ``datasource`` (a region, a chart, a list in list mode) -- for
    ``request``: ``{'b', 'preview', 'template', 'url', 'group', 'columns'}``.

    ``datasource_url`` is the URL of the data source API the panel counts
    with (by default ``reverse('gtdatasource', name=build.datasource)``);
    ``group`` is ``gtdesign:<target>``, the state the target (and every
    node ``filtered_by`` the panel) follows.

    No published :class:`~djgentelella.designs.models.Page` is needed: code
    generated from a design (djgentelella-editor) calls it with its own
    build. ``None`` when ``request`` may not see it: without
    ``build.perms`` or the data source's ``has_permission``.

    A panel over a table of a model (no ``build.datasource``) counts through
    its own endpoint (:func:`~djgentelella.designs.factories.
    facets_viewset_for`): ``url`` is where it is mounted, and ``target`` the
    build of the table (by default ``build.target_build``), whose
    ``column_conditions`` leave out the facets of the columns it hides.
    Without ``url``, ``ValueError``.
    """
    if not build.datasource:
        if url is None:
            raise ValueError('facets panel %r is not over a data source: give the '
                             'url of its facets_viewset_for()' % (build.id,))
        if request is None:
            return None
        return model_facets_context(build, request, url,
                                    target if target is not None
                                    else build.target_build)
    if request is None:
        return None
    return source_facets_context(build, request, getattr(request, 'user', None),
                                 datasource_url)


def model_facets_context(build, request, url, target=None):
    """The context of :data:`FACETS_TEMPLATE` for a panel over a table of a
    model, served at ``url``; ``None`` without ``build.perms``."""
    user = getattr(request, 'user', None)
    if build.model is None or user is None or \
            not all_permission(user, list(build.perms)):
        return None
    hidden = hidden_columns(target, request) \
        if getattr(target, 'column_conditions', None) else set()
    shown = copy.copy(build)
    shown.columns = [name for name in build.columns if name not in hidden]
    if not shown.columns:
        return None
    return {'b': shown, 'preview': False, 'template': FACETS_TEMPLATE, 'url': url,
            'group': 'gtdesign:%s' % build.target, 'columns': ','.join(shown.columns)}


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
        components that declare ``facets_target`` -- over a data source, and
        with ``facets_model`` over an exposed model too."""
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
        if target is not None and target.get('type') in TABLE_TYPES and \
                (target.get('props') or {}).get('datasource'):
            # A table in list mode: over its data source, like a region.
            return self.resolve_source(node, rctx, path, build,
                                       rctx.component(target['type']), target)
        over_model = False
        if target is not None and target.get('type') not in TABLE_TYPES:
            component = rctx.component(target.get('type'))
            if component is not None and getattr(component, 'facets_target', False):
                target_props = target.get('props') or {}
                if not (getattr(component, 'facets_model', False)
                        and target_props.get('model')
                        and not target_props.get('datasource')):
                    return self.resolve_source(node, rctx, path, build, component,
                                               target)
                # A node over an exposed model (a region, a grid): counted
                # like a table, through the panel's own endpoint.
                over_model = True
        if target is None or (target.get('type') not in TABLE_TYPES
                              and not over_model):
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
            return render_to_string(FACETS_TEMPLATE, context)
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
        return render_to_string(FACETS_TEMPLATE, context)

    def render_source(self, build, rctx):
        context = {'b': build, 'preview': rctx.preview}
        if rctx.preview:
            context['facets'] = [(name, ['%s 1' % _('Value'), '%s 2' % _('Value')])
                                 for name in build.columns]
            return render_to_string(FACETS_TEMPLATE, context)
        context = source_facets_context(build, rctx.request, rctx.user)
        if context is None:
            return no_permission(build)
        return render_to_string(FACETS_TEMPLATE, context)

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
