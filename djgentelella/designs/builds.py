"""The builds of the components with data: what a node resolves to.

They hold data -- model classes, field names, permissions, choices -- and
never source code: ``ChartBuild`` keeps ``group_by='available_since'`` and
``period='month'``, not ``"TruncMonth('available_since')"``. The runtime
(:mod:`djgentelella.designs.factories`) builds serializers, filters and
viewsets from them while serving; djgentelella-editor derives the text of its
generated code from the same data.

Every build carries the hash of the document it comes from (``page_hash``):
with the node id it is the key the factories cache their classes by, so a
page published again with a different document gets new classes.
"""

from dataclasses import dataclass, field

from djgentelella.designs.components import NodeBuild

__all__ = ['ACTION_PERMISSIONS', 'AGGREGATES', 'CHART_TYPES', 'CRUD_PERMISSIONS',
           'CRUD_VIEWS', 'ChartBuild', 'CrudBuild', 'DataBuild', 'FacetsBuild',
           'NotifyAction', 'NotifyBuild', 'ObjectManagementBuild', 'PERIODS',
           'RowLink', 'StatBuild', 'TABLE_ACTIONS']

#: ObjectManagement actions and the model permission each one needs by default.
ACTION_PERMISSIONS = {
    'list': 'view',
    'retrieve': 'view',
    'detail_template': 'view',
    'get_values_for_update': 'change',
    'create': 'add',
    'update': 'change',
    'partial_update': 'change',
    'destroy': 'delete',
}
#: The kinds of chart, as djgentelella.chartjs classes know them.
CHART_TYPES = ('bar', 'horizontal_bar', 'line', 'pie', 'doughnut')
AGGREGATES = ('count', 'sum', 'avg', 'min', 'max')
#: Periods a date can be grouped or compared by (djgentelella.datasources).
PERIODS = ('day', 'week', 'month', 'quarter', 'year')
#: The actions of a table a condition can refuse (``action_conditions``),
#: and the viewset actions each one covers.
TABLE_ACTIONS = {
    'create': ('create',),
    'update': ('update', 'partial_update', 'get_values_for_update'),
    'destroy': ('destroy',),
    'retrieve': ('retrieve', 'detail_template'),
}
#: The pages of a classic CRUD and the model permission of each one.
CRUD_VIEWS = ('list', 'create', 'detail', 'update', 'delete')
CRUD_PERMISSIONS = {'list': 'view', 'detail': 'view', 'create': 'add',
                    'update': 'change', 'delete': 'delete'}


@dataclass
class DataBuild(NodeBuild):
    """What every component with data has."""

    #: sha256 of the document (``Page.hash``); with ``id``, the cache key.
    page_hash: str = ''
    #: Resolved for the editor's preview: no rows, sample data.
    preview: bool = False
    title: str = ''
    #: The columns a data source over the node's model offers: the fields its
    #: exposure allows, for the filters, facets and aggregates of the
    #: parameter document of :mod:`djgentelella.datasources.query`.
    columns: list = field(default_factory=list)


@dataclass
class RowLink:
    """A per row link to a page about one object.

    Either ``url_name`` -- a URL of the project that takes the row pk --,
    ``page`` -- the path of a design page with ``meta.parent`` -- or
    ``flow`` -- the name of a flow of djgentelella.flows over the row's
    model: its ``flow_detail``, or with ``transition`` the page that runs
    that transition.
    """

    title: str
    icon: str = 'fa fa-external-link'
    url_name: str = ''
    page: str = ''
    flow: str = ''
    transition: str = ''
    #: A condition of :mod:`djgentelella.authorization`: the link only shows
    #: where it holds.
    condition: object = None


@dataclass
class NotifyAction:
    """One notification of a table: on ``event``, ``kind`` to ``to``."""

    event: str
    kind: str
    to: list
    code: str = ''
    subject: str = ''
    message: str = ''
    message_type: str = 'info'

    @property
    def email(self):
        return self.kind == 'email'


@dataclass
class NotifyBuild:
    model: type
    actions: list = field(default_factory=list)
    #: The fields of the row the texts can read (those its exposure allows).
    fields: list = field(default_factory=list)

    @property
    def events(self):
        return [action.event for action in self.actions]

    def actions_for(self, event):
        return [action for action in self.actions if action.event == event]


@dataclass
class ObjectManagementBuild(DataBuild):
    """A DataTable of a model with create, update, detail and delete modals."""

    model: type = None
    #: The :class:`~djgentelella.designs.forms.FormBuild` of the modals.
    form: object = None
    list_fields: list = field(default_factory=list)
    search_fields: list = field(default_factory=list)
    ordering: list = field(default_factory=list)
    #: ``{viewset action: [app.codename, ...]}``, every one required.
    perms: dict = field(default_factory=dict)
    #: Inline: the rows are the children of the page's parent object, through
    #: this foreign key.
    parent_field: str = None
    parent_model: type = None
    #: What reaching a parent's rows needs: the parent model's view perms.
    parent_perms: list = field(default_factory=list)
    row_links: list = field(default_factory=list)
    notify: NotifyBuild = None
    #: ``{list field: select2 lookup basename}`` of the relation columns that
    #: can be filtered with an autocomplete.
    lookups: dict = field(default_factory=dict)
    #: ``{list field: condition}`` and ``{action: condition}``, see
    #: :mod:`djgentelella.designs.conditions`; actions are ``create``,
    #: ``update``, ``destroy`` and ``retrieve``.
    column_conditions: dict = field(default_factory=dict)
    action_conditions: dict = field(default_factory=dict)

    @property
    def inline(self):
        return self.parent_field is not None


@dataclass
class ChartBuild(DataBuild):
    """One aggregate of a model or a data source, grouped by a column."""

    model: type = None
    #: Name of a djgentelella.datasources data source, instead of ``model``.
    datasource: str = ''
    chart: str = 'bar'
    group_by: str = ''
    #: For a date ``group_by``: one of :data:`PERIODS`.
    period: str = None
    aggregate: str = 'count'
    value_field: str = None
    limit: int = 10
    perms: list = field(default_factory=list)

    @property
    def circular(self):
        return self.chart in ('pie', 'doughnut')


@dataclass
class StatBuild(DataBuild):
    """A tile with one number, optionally compared with the previous period."""

    subtitle: str = ''
    icon: str = 'fa fa-cubes'
    model: type = None
    datasource: str = ''
    aggregate: str = 'count'
    value_field: str = None
    #: The date column and the period of the comparison, or ``None``.
    compare_field: str = None
    period: str = 'month'
    perms: list = field(default_factory=list)


@dataclass
class CrudBuild(DataBuild):
    """djgentelella's classic CRUD (``CRUDView``): server rendered pages."""

    model: type = None
    form: object = None
    list_fields: list = field(default_factory=list)
    search_fields: list = field(default_factory=list)
    #: The fields of the detail page.
    detail_fields: list = field(default_factory=list)
    views: list = field(default_factory=lambda: list(CRUD_VIEWS))
    #: ``{view: [app.codename, ...]}``.
    perms: dict = field(default_factory=dict)
    #: ``'embed'``: the list in the page; ``'link'``: a tile opening it.
    mode: str = 'embed'
    paginate_by: int = 10
    #: ``{list or detail field: condition}`` and ``{page: condition}``,
    #: see :mod:`djgentelella.designs.conditions`; pages are ``create``,
    #: ``detail``, ``update`` and ``delete``.
    column_conditions: dict = field(default_factory=dict)
    action_conditions: dict = field(default_factory=dict)


@dataclass
class FacetsBuild(DataBuild):
    """A facets panel over the rows of another node, a table."""

    #: Id of the table node it filters.
    target: str = ''
    #: Here, the columns with a facet: the panel offers nothing else.
    columns: list = field(default_factory=list)
    model: type = None
    perms: list = field(default_factory=list)
    #: Whether the target is an inline table: the facets then count the
    #: children of the page's parent.
    inline: bool = False
    #: For a target of another component (``facets_target``): the data
    #: source its rows come from, served by the data source API.
    datasource: str = ''
