"""Runtime components: what each ``type`` of design node does.

A :class:`RuntimeComponent` says where its nodes may go (``parent_types``,
``container``), validates their props (``props_schema``, :meth:`check_props`),
checks them against the project and turns them into a *build*
(:meth:`~RuntimeComponent.resolve`), and renders a build as final HTML
(:meth:`~RuntimeComponent.render`). Builds are dataclasses holding data --
model classes, field names, choices -- never source code: generating code is
djgentelella-editor's job, on top of the same components.

Components are registered in :mod:`djgentelella.designs.registry`.
"""

import copy
from dataclasses import dataclass, field

from django.apps import apps
from django.contrib.auth.models import Permission
from django.db.models import Q
from django.utils.safestring import mark_safe

from djgentelella.designs import exposure
from djgentelella.designs.forms import build_form, registered_lookups
from djgentelella.designs.jsonschema import Error, validate
from djgentelella.sites import get_current_site

__all__ = ['Endpoint', 'Error', 'NodeBuild', 'ResolveContext', 'RuntimeComponent']


@dataclass
class NodeBuild:
    """The build of a node that needs nothing but its own props."""

    id: str
    type: str
    props: dict = field(default_factory=dict)


@dataclass
class Endpoint:
    """A viewset served under ``gtapis/designs/<page>/<node>/<suffix>``.

    ``suffix`` is a DRF router prefix: ``''`` for the node itself, or
    ``'chart'``, ``'lookup/<model>'``... The viewset reads the page and the
    build it serves from ``request.gtdesign_page`` and ``request.gtdesign_build``.
    """

    suffix: str
    viewset: type
    basename: str


class RuntimeComponent:
    """A node type of the design tree, as djgentelella serves it."""

    type = ''
    label = ''
    icon = 'fa fa-square-o'
    #: Whether the node may have children.
    container = False
    #: Types of node it may be placed in; ``()`` means it is the root.
    parent_types = ('col',)
    #: JSON Schema of ``node["props"]``. ``x-widget`` hints are for the editor.
    props_schema = {'type': 'object', 'additionalProperties': False, 'properties': {}}
    #: Props of a node freshly dropped from the editor's palette.
    default_props = {}

    def check_props(self, node, path):
        """:class:`Error` list of the props' shape; by default, the schema."""
        props = node.get('props', {})
        return validate(props, self.props_schema, path + '.props')

    def resolve(self, node, rctx, path):
        """Check the node against the project and return its build.

        Report problems with ``rctx.error(path, message)``; the engine counts
        them, so returning a build after an error is fine.
        """
        return NodeBuild(node['id'], node['type'], dict(node.get('props') or {}))

    def render(self, build, rctx, children):
        """The node's final HTML, already escaped; ``children`` is safe HTML."""
        return mark_safe(children)

    def media(self, build, rctx):
        """``{'js': [urls], 'css': [urls], 'inline_js': str}``; all optional."""
        return {}

    def endpoints(self, build):
        """The :class:`Endpoint` list the node serves; most serve none."""
        return []

    #: Whether a ``facets`` panel may name a node of this type as its
    #: ``target``; it then asks :meth:`facets_source` what it filters.
    facets_target = False

    def facets_source(self, node, rctx, path):
        """The name of the DataSource (:mod:`djgentelella.datasources`) a
        facets panel over
        ``node`` counts and filters, or ``None`` after reporting why it cannot.

        Only asked when :attr:`facets_target` is true. ``node`` is the target
        as the document has it, not resolved yet. The panel talks to the data
        source API (``gtdatasource``), and shares the ``GTDataSourceState``
        group ``gtdesign:<node id>``: the target's widget must join that
        group to be filtered.
        """
        return None


class ResolveContext:
    """What a component sees while resolving or rendering one design."""

    def __init__(self, design, request=None, preview=False, *, site=None,
                 user=None, allow_templates=False):
        self.design = design
        self.request = request
        self.site = site if site is not None else (
            get_current_site(request) if request is not None else None)
        self.user = user if user is not None else getattr(request, 'user', None)
        #: Querysets go empty: the editor's preview shows structure, not rows.
        self.preview = preview
        #: Whether the ``html`` component may be a Django template (see
        #: :func:`djgentelella.designs.engine.page_trust`).
        self.allow_templates = allow_templates
        self.errors = []
        self._forms = {}
        #: ``{type: RuntimeComponent}`` the design is resolved with; ``None``
        #: means the registry's (:mod:`djgentelella.designs.registry`).
        #: :func:`~djgentelella.designs.engine.resolve` sets it.
        self.components = None
        #: The :class:`~djgentelella.designs.engine.ResolvedPage` being
        #: rendered; ``None`` while resolving.
        self.resolved = None

    def copy_for(self, request):
        """A copy of this context to render the same design for
        ``request``: the same class and attributes -- whatever a subclass's
        ``__init__`` took -- with that request, its site and user, and
        nothing collected yet (no errors, forms or resolved page).

        :func:`~djgentelella.designs.engine.render` calls it on the instance
        a page was resolved with. A subclass that keeps other state per
        request resets it here.
        """
        clone = copy.copy(self)
        if request is not self.request:
            clone.request = request
            clone.site = get_current_site(request) if request is not None else None
            clone.user = getattr(request, 'user', None)
        clone.errors = []
        clone._forms = {}
        clone.resolved = None
        return clone

    def error(self, path, message):
        self.errors.append(Error(path, str(message)))

    def has_errors_under(self, path):
        return any(error.path == path or error.path.startswith(path + '.')
                   or error.path.startswith(path + '[') for error in self.errors)

    def exposure(self, label, path=None):
        """The :class:`~djgentelella.designs.exposure.Exposure` of ``label``,
        or ``None`` after reporting why the design cannot use it.

        The hook every component asks which models a design may use
        (:mod:`djgentelella.designs.exposure`):
        a subclass that answers otherwise (djgentelella-editor's, which takes
        every model) changes them all. With ``path=None`` nothing is
        reported: it only asks.
        """
        if path is None:
            if not isinstance(label, str) or '.' not in label:
                return None
            return exposure.get_exposure(label)
        if not isinstance(label, str) or '.' not in label:
            self.error(path, '%r is not an "app.Model" label' % (label,))
            return None
        found = exposure.get_exposure(label)
        if found is not None:
            return found
        try:
            apps.get_model(label)
        except (LookupError, ValueError):
            self.error(path, 'unknown model %r' % label)
        else:
            self.error(path, 'model %r is not exposed to designs: call '
                             'djgentelella.designs.exposure.expose() on it from '
                             'a gtdesigns.py' % label)
        return None

    def model(self, label, path):
        """The model class of ``label``, only if it is exposed
        (:mod:`djgentelella.designs.exposure`)."""
        found = self.exposure(label, path)
        return found.model if found is not None else None

    def check_permissions(self, path, perms):
        """Report each of ``perms`` (``app.codename``) that does not exist,
        and an empty list, which ``AllPermissionByAction`` would read as
        "nobody".

        The hook of every permission a design names -- ``meta.permissions``
        (only when it has some) and the ``perms`` of the components with
        data. By default they are looked up in ``auth_permission``; a
        subclass can read them elsewhere (the models' ``Meta``, before
        ``migrate``).
        """
        if not perms:
            self.error(path, 'cannot be empty: AllPermissionByAction refuses an '
                             'action without permissions')
            return
        query = Q(pk__in=[])
        for perm in perms:
            app_label, _dot, codename = str(perm).partition('.')
            query |= Q(content_type__app_label=app_label, codename=codename)
        found = {'%s.%s' % pair for pair in Permission.objects.filter(query)
                 .values_list('content_type__app_label', 'codename')}
        for perm in perms:
            if perm not in found:
                self.error(path, 'unknown permission %r' % (perm,))

    def lookups(self, model):
        """Basenames of the select2 lookups a design may use for ``model``,
        the first one preferred: what autocomplete widgets of its forms and
        the filters of its tables' relation columns are built with.

        By default the lookups registered in a ``gtselects.py``; a subclass
        can offer others (djgentelella-editor generates them).
        """
        return registered_lookups(model)

    def component(self, node_type):
        """The :class:`RuntimeComponent` of ``node_type`` the design is
        resolved with, or ``None``."""
        if self.components is None:
            # The registry imports the components with data, which import
            # this module.
            from djgentelella.designs import registry  # noqa: PLC0415 (circular)
            return registry.get_component(node_type)
        return self.components.get(node_type)

    def form(self, key, path):
        """The :class:`~djgentelella.designs.forms.FormBuild` of ``forms[key]``."""
        forms = self.design.get('forms') or {}
        if key not in forms:
            self.error(path, 'no form %r in "forms"' % (key,))
            return None
        if key not in self._forms:
            self._forms[key] = build_form(key, forms[key], self, '$.forms.' + key)
        return self._forms[key]

    def datasource(self, name, path):
        """The DataSource ``name`` (:mod:`djgentelella.datasources`), or
        ``None`` after an error."""
        if not apps.is_installed('djgentelella.datasources'):
            self.error(path, 'data source %r needs djgentelella.datasources in '
                             'INSTALLED_APPS' % (name,))
            return None
        # Optional app: only importable when it is installed (checked above).
        from djgentelella.datasources.base import get_datasource  # noqa: PLC0415
        try:
            source = get_datasource(name)
        except (KeyError, LookupError):
            source = None
        if source is None:
            self.error(path, 'unknown data source %r' % (name,))
        elif self.request is not None and not source.has_permission(self.request):
            self.error(path, 'no permission for data source %r' % (name,))
            return None
        return source
