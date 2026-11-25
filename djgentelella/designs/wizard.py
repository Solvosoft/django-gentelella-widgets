"""The ``wizard`` component: a form in several steps over one exposed model.

::

    {"type": "wizard", "id": "hire", "props": {
        "model": "demoapp.Employee",
        "title": "New employee",
        "site_field": "site",
        "draft": "model",
        "steps": [
            {"name": "personal", "title": "Personal data",
             "fields": ["name", "email", "has_car"]},
            {"name": "vehicle", "title": "Vehicle", "fields": ["plate"],
             "when": {"field": "has_car", "equals": true}},
            {"name": "contract", "title": "Contract",
             "fields": ["department", "salary", "contract"],
             "condition": {"perm": "demoapp.change_employee"}}]}}

Each step is a form of the model (its ``fields``, ``render``, ``grid``,
``widgets`` and ``help``, as an entry of the design's ``forms``); one object
is created -- or, with ``"mode": "edit"`` on a page about one object of the
model (``meta.parent``), edited -- when the wizard finishes, in one
transaction. A step is skipped while its ``condition``
(:mod:`djgentelella.authorization`) or its ``when`` (a value of a field of
an earlier step) does not hold.

It is :class:`~djgentelella.wizard.views.GTWizardView` served by the design
router: the page renders the current step and the form posts to the node's
endpoint, which redirects back to the page (also when a step has errors: the
state remembers them). No javascript is needed to move between steps.

Permissions: ``perms.create`` (by default the model's ``add``) or
``perms.update`` (``change``) to see and post it, plus, when editing, the
page's own rule for its object (the ``view`` permission of the model).
``site_field`` -- a foreign key to ``sites.Site`` -- is set to the current
Site on creation, and an object of another Site cannot be edited (404).
``optimistic_lock`` (edit only) refuses to finish when the object changed
after the wizard started.

``pipeline`` (:mod:`djgentelella.designs.pipeline`, ``on_submit``) on a step
runs its validations and computations whenever the step validates -- an
error keeps the user in the step, a computed value is kept in the draft --;
a process or a branch there is an error. On the wizard it runs when it
finishes: validations and computations, then the save and the processes in
one transaction (a failing process rolls everything back and the wizard
stays at its last step), and the branch that holds is where it goes instead
of ``success_url``.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import Http404, HttpResponseRedirect
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.renderers import JSONRenderer

from djgentelella.authorization import evaluate_condition, validate_condition
from djgentelella.designs import pipeline
from djgentelella.designs.builds import DataBuild
from djgentelella.designs.components import Endpoint, RuntimeComponent
from djgentelella.designs.data_components import (
    PERMISSION_LIST, allowed_fields, can, check_permissions, columns_of,
    data_build, endpoint_url, no_permission, plural,
)
from djgentelella.designs.factories import valid_pk
from djgentelella.designs.forms import RENDERS, build_form, is_form_field, no_field
from djgentelella.designs.models import normalize_path
from djgentelella.forms import widgetmap
from djgentelella.permission_management import all_permission
from djgentelella.sites import get_current_site, site_pk, site_q
from djgentelella.wizard import conf
from djgentelella.wizard.views import GTWizardView, Step

__all__ = ['WIZARD_COMPONENTS', 'WizardBuild', 'WizardComponent', 'WizardStepBuild',
           'WizardViewSet', 'design_wizard_view', 'when_holds']

TEMPLATE = 'gtdesigns/components/wizard.html'
STEP_NAME = r'^[a-z][a-z0-9_]{0,39}$'
MODES = ('create', 'edit')
#: What a file field gets by default in a wizard: an upload in chunks, the
#: only kind a draft can keep.
UPLOAD_WIDGET = 'FileChunkedUpload'
FILE_KINDS = ('file', 'image')
WHEN_OPERATORS = ('equals', 'in', 'filled')


@dataclass
class WizardStepBuild:
    name: str
    title: str
    #: :class:`~djgentelella.designs.forms.FormBuild` of the step.
    form: object = None
    description: str = ''
    #: Condition of :mod:`djgentelella.authorization`, or ``None``.
    condition: dict = None
    #: ``{"field", "step", "equals" | "in" | "filled"}``, or ``None``.
    when: dict = None
    #: Its ``on_submit`` :class:`~djgentelella.designs.pipeline.PipelineBuild`
    #: (validations and computations only), or ``None``.
    pipeline: object = None


@dataclass
class WizardBuild(DataBuild):
    model: type = None
    mode: str = 'create'
    steps: list = field(default_factory=list)
    #: ``{"create": [perms], "update": [perms]}``.
    perms: dict = field(default_factory=dict)
    site_field: str = ''
    draft: str = 'session'
    optimistic_lock: bool = False
    #: ``"page:<path>"``, a URL name without arguments, or ``""`` (the page).
    success_url: str = ''
    success_message: str = ''
    #: The model of ``meta.parent`` when editing (the same as ``model``).
    parent_perms: list = field(default_factory=list)

    @property
    def action(self):
        return 'update' if self.mode == 'edit' else 'create'


def normalized(value):
    """A cleaned value as JSON compares it: a row by its pk, a decimal or a
    date as text, a list item by item."""
    if isinstance(value, models.Model):
        return value.pk
    if isinstance(value, (list, tuple)) or hasattr(value, 'model'):
        return [normalized(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def same(value, expected):
    value = normalized(value)
    return value == expected or (
        not isinstance(value, (list, dict, bool)) and value is not None
        and not isinstance(expected, bool) and str(value) == str(expected))


def when_holds(when, value):
    """Whether the ``when`` of a step holds for the cleaned ``value``."""
    if 'filled' in when:
        filled = value not in (None, '', [], ()) and not (
            hasattr(value, 'exists') and not value.exists())
        return filled is bool(when['filled'])
    if 'in' in when:
        return any(same(value, item) for item in when['in'])
    return same(value, when['equals'])


def step_condition(build, step):
    """The callable condition of ``step`` for :class:`Step`."""
    if step.condition is None and step.when is None:
        return None

    def applies(wizard):
        if step.condition is not None and not evaluate_condition(
                step.condition, wizard.request, wizard.get_object()):
            return False
        if step.when is not None:
            value = wizard.cleaned_data_for(step.when['step']).get(step.when['field'])
            if not when_holds(step.when, value):
                return False
        return True
    return applies


class DesignWizardView(GTWizardView):
    """:class:`GTWizardView` of a :class:`WizardBuild`, for one request of
    its page or its endpoint."""

    errors_by_redirect = True

    def __init__(self, build, request, page, parent=None):
        super().__init__()
        self.build = build
        self.request = request
        self.args, self.kwargs = (), {}
        self.page = page
        self.parent = parent
        self.model = build.model
        self.title = build.title
        self.draft_storage = build.draft
        self.optimistic_lock = build.optimistic_lock
        self.success_message = build.success_message or _('Saved.')
        self.pipeline = build.pipeline
        self.pipeline_node = build.id

    def get_steps(self):
        return [Step(step.name, step.form.form_class, step.title,
                     condition=step_condition(self.build, step),
                     description=step.description, pipeline=step.pipeline)
                for step in self.build.steps]

    def get_step_pipeline(self, step):
        # Resolved with the document: a PipelineBuild already.
        return step.pipeline or None

    def get_pipeline(self):
        return self.build.pipeline or None

    def get_object(self):
        return self.parent if self.build.mode == 'edit' else None

    def get_wizard_key(self):
        key = 'gtdesign:%s:%s' % (self.page.path, self.build.id)
        if self.parent is not None:
            key = '%s:%s' % (key, self.parent.pk)
        return key[:255]

    def get_page_url(self):
        path = self.page.path
        if self.parent is not None:
            path = '%s/%s' % (path, self.parent.pk)
        return reverse('gt-design-page', args=[path])

    def get_action_url(self):
        parts = (self.parent.pk,) if self.parent is not None else ()
        rest = ''.join('%s/' % part for part in parts)
        return reverse('gt-design-endpoint', kwargs={
            'page_id': self.page.pk, 'node_id': self.build.id, 'rest': rest})

    def get_draft_url(self, draft_id):
        # The page does not read ?draft=: the endpoint resumes it and
        # redirects to the page.
        return '%s?%s' % (self.get_action_url(), urlencode({'draft': draft_id}))

    def get_success_url(self):
        target = self.build.success_url
        if not target:
            return self.get_page_url()
        if target.startswith('page:'):
            return reverse('gt-design-page', args=[normalize_path(target[5:])])
        return reverse(target)

    def done(self, forms):
        values = self.extra_values(forms)
        if self.build.site_field and self.build.mode == 'create':
            values[self.build.site_field + '_id'] = site_pk(
                get_current_site(self.request))
        self.object = self.save_object(forms, **values)
        return None


def design_wizard_view(build, request, page, parent=None):
    return DesignWizardView(build, request, page, parent)


def site_allows(build, obj, request):
    """Whether ``obj`` may be edited from the request's Site."""
    if not build.site_field or obj is None:
        return True
    return build.model._default_manager.filter(
        site_q(get_current_site(request), field=build.site_field),
        pk=obj.pk).exists()


class WizardViewSet(viewsets.ViewSet):
    """The endpoint of a ``wizard`` node: ``POST`` runs a step, ``GET``
    resumes a draft (``?draft=<id>``) or goes back to the page."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = ()
    renderer_classes = (JSONRenderer,)

    def wizard(self, request, parent_pk=None):
        build = request.gtdesign_build
        if build.model is None:
            raise Http404
        user = request.user
        if not all_permission(user, list(build.perms[build.action])):
            raise PermissionDenied()
        parent = None
        if build.mode == 'edit':
            if parent_pk is None or not valid_pk(build.model, parent_pk):
                raise Http404
            if not all_permission(user, list(build.parent_perms)):
                raise PermissionDenied()
            parent = build.model._default_manager.filter(pk=parent_pk).first()
            if parent is None or not site_allows(build, parent, request):
                raise Http404
        return DesignWizardView(build, request._request, request.gtdesign_page,
                                parent)

    def list(self, request, parent_pk=None):
        view = self.wizard(request, parent_pk)
        draft_id = request.query_params.get('draft')
        if draft_id:
            return view.resume(draft_id)
        return HttpResponseRedirect(view.get_page_url())

    def create(self, request, parent_pk=None):
        # Also for anonymous users (a page without login): SessionAuthentication
        # checks CSRF only for signed-in ones.
        SessionAuthentication().enforce_csrf(request)
        view = self.wizard(request, parent_pk)
        return view.post(request._request)


def wizard_schema():
    step = {
        'type': 'object',
        'required': ['name', 'fields'],
        'additionalProperties': False,
        'properties': {
            'name': {'type': 'string', 'pattern': STEP_NAME,
                     'title': 'Name (a form prefix: a-z, 0-9, _)'},
            'title': {'type': 'string', 'title': 'Title'},
            'description': {'type': 'string', 'title': 'Text above the form'},
            'fields': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1,
                       'x-widget': 'model-fields', 'title': 'Fields of the step'},
            'render': {'enum': list(RENDERS), 'title': 'Form layout'},
            'grid': {'type': 'array', 'x-widget': 'form-grid',
                     'title': 'Grid (render "as_grid")'},
            'widgets': {'type': 'object', 'x-widget': 'widgets',
                        'additionalProperties': {'type': 'string'},
                        'title': 'Widget per field'},
            'help': {'type': 'object', 'x-widget': 'help',
                     'additionalProperties': {'type': 'object'},
                     'title': 'Help per field'},
            'condition': {'x-widget': 'condition',
                          'title': 'Step shown only when (user, group, flag...)'},
            'pipeline': {**pipeline.PIPELINE_SCHEMA,
                         'title': 'Pipeline each time the step validates '
                                  '(validations and computations)'},
            'when': {
                'type': 'object', 'x-widget': 'step-when',
                'title': 'Step shown only when a field of an earlier step...',
                'required': ['field'],
                'additionalProperties': False,
                'properties': {
                    'field': {'type': 'string', 'x-widget': 'model-field',
                              'title': 'Field of an earlier step'},
                    'equals': {'title': 'equals'},
                    'in': {'type': 'array', 'title': 'is one of'},
                    'filled': {'type': 'boolean', 'title': 'is filled (true) or '
                                                           'empty (false)'},
                },
            },
        },
    }
    return {
        'type': 'object',
        'required': ['model', 'steps'],
        'additionalProperties': False,
        'properties': {
            'model': {'type': 'string', 'x-widget': 'model', 'title': 'Model'},
            'title': {'type': 'string', 'title': 'Title'},
            'mode': {'enum': list(MODES),
                     'title': 'Create an object, or edit the one of the page '
                              '(meta.parent)'},
            'steps': {'type': 'array', 'minItems': 1, 'items': step,
                      'x-widget': 'wizard-steps', 'title': 'Steps'},
            'perms': {
                'type': 'object', 'x-widget': 'perms',
                'title': 'Permissions (empty = the model add / change)',
                'additionalProperties': False,
                'properties': {'create': PERMISSION_LIST, 'update': PERMISSION_LIST},
            },
            'site_field': {'type': 'string', 'x-widget': 'model-field',
                           'x-filter': 'site',
                           'title': 'Foreign key to the Site (set on creation; '
                                    "only the current Site's objects are edited)"},
            'draft': {'enum': list(conf.STORAGES),
                      'title': 'Drafts kept in the session or in the database'},
            'optimistic_lock': {
                'type': 'boolean', 'default': False,
                'title': 'Refuse to finish when the object changed after the '
                         'wizard started (edit mode)'},
            'success_url': {'type': 'string', 'x-widget': 'link',
                            'title': 'Where to go when it finishes: '
                                     '"page:<path>" or a URL name (empty: this '
                                     'page)'},
            'success_message': {'type': 'string', 'title': 'Message when it '
                                                           'finishes'},
            'pipeline': {**pipeline.PIPELINE_SCHEMA,
                         'title': 'Pipeline when the wizard finishes'},
        },
    }


class WizardComponent(RuntimeComponent):
    """A form in several steps with a progress bar and drafts
    (:mod:`djgentelella.wizard`)."""

    type = 'wizard'
    label = gettext_lazy('Wizard (form in steps)')
    icon = 'fa fa-list-ol'
    props_schema = wizard_schema()
    default_props = {'steps': [{'name': 'step1', 'title': 'Step 1', 'fields': []}]}

    def resolve(self, node, rctx, path):
        props = node.get('props') or {}
        build = data_build(WizardBuild, node, rctx, mode=props.get('mode', 'create'),
                           draft=props.get('draft') or conf.default_storage(),
                           success_message=props.get('success_message', ''))
        found = rctx.exposure(props['model'], path + '.props.model')
        if found is None:
            return build
        model = found.model
        by_name = allowed_fields(found)
        if build.mode == 'edit':
            parent = (rctx.design.get('meta') or {}).get('parent') or {}
            label = parent.get('model') if isinstance(parent, dict) else None
            if not isinstance(label, str) or label.lower() != model._meta.label_lower:
                rctx.error(path + '.props.mode', _(
                    'a wizard that edits needs a page about one %s (meta.parent)')
                    % model._meta.label)
        elif props.get('optimistic_lock'):
            rctx.error(path + '.props.optimistic_lock', _(
                'optimistic locking is for a wizard that edits (mode "edit")'))

        site_field = props.get('site_field') or ''
        if site_field:
            model_field = next((item for item in model._meta.get_fields()
                                if item.name == site_field), None)
            related = getattr(model_field, 'related_model', None)
            if model_field is None or not model_field.many_to_one or \
                    related is None or related._meta.label_lower != 'sites.site':
                rctx.error(path + '.props.site_field',
                           _('%(field)r is not a foreign key of %(model)s to '
                             'sites.Site') % {'field': site_field,
                                              'model': model._meta.label})

        steps, placed = [], {}
        for index, data in enumerate(props.get('steps') or []):
            where = '%s.props.steps[%d]' % (path, index)
            step = self.resolve_step(node, rctx, where, data, props['model'],
                                     by_name, placed, site_field, found)
            if any(item.name == data['name'] for item in steps):
                rctx.error(where + '.name', _('step %r is repeated') % data['name'])
            if step is not None:
                steps.append(step)
            for name in data.get('fields') or []:
                placed.setdefault(name, data['name'])

        on_submit = pipeline.resolve_pipeline(
            rctx, props, path, event=pipeline.ON_SUBMIT, model=model, exposure=found,
            form_fields=list(placed))

        if build.mode == 'create' and not rctx.has_errors_under(path + '.props.steps'):
            for model_field in model._meta.concrete_fields:
                if model_field.name in placed or model_field.name == site_field \
                        or not is_form_field(model_field):
                    continue
                if not model_field.blank and not model_field.has_default() and \
                        not model_field.null:
                    rctx.error(path + '.props.steps', _(
                        '%(field)r is required by %(model)s and no step asks '
                        'for it') % {'field': model_field.name,
                                     'model': model._meta.label})

        perms = {'create': found.permissions('add'),
                 'update': found.permissions('change')}
        perms.update(props.get('perms') or {})
        for action, needed in perms.items():
            check_permissions(rctx, path + '.props.perms.' + action, needed)

        success_url = props.get('success_url') or ''
        if success_url and not success_url.startswith('page:'):
            try:
                reverse(success_url)
            except NoReverseMatch:
                rctx.error(path + '.props.success_url', _(
                    '%r is neither "page:<path>" nor a URL name that takes no '
                    'arguments') % (success_url,))
        if rctx.has_errors_under(path):
            return build
        if props.get('title'):
            build.title = props['title']
        elif build.mode == 'create':
            build.title = _('New %s') % model._meta.verbose_name
        else:
            build.title = plural(model)
        build.model = model
        build.steps = steps
        build.perms = perms
        build.parent_perms = found.permissions('view') if build.mode == 'edit' else []
        build.site_field = site_field
        build.optimistic_lock = bool(props.get('optimistic_lock'))
        build.success_url = success_url
        build.columns = columns_of(found)
        build.pipeline = on_submit
        return build

    def resolve_step(self, node, rctx, where, data, label, by_name, placed,
                     site_field, found=None):
        names = list(data.get('fields') or [])
        for name in names:
            if name in placed:
                rctx.error(where + '.fields', _(
                    '%(field)r is already in step %(step)r') % {
                        'field': name, 'step': placed[name]})
            elif name == site_field:
                rctx.error(where + '.fields', _(
                    '%r is the site_field: the wizard sets it') % (name,))
        widgets = dict(data.get('widgets') or {})
        for name in names:
            if name in by_name and widgetmap.field_kind(by_name[name]) in FILE_KINDS:
                widgets.setdefault(name, UPLOAD_WIDGET)
                if widgets[name] not in widgetmap.UPLOAD_WIDGETS:
                    rctx.error(where + '.widgets.' + name, _(
                        'a file of a wizard is uploaded in chunks (one of %s): a '
                        'draft cannot keep a plain file input')
                        % ', '.join(sorted(widgetmap.UPLOAD_WIDGETS)))
        form_data = {'model': label, 'fields': names, 'widgets': widgets}
        for key in ('render', 'grid', 'help'):
            if key in data:
                form_data[key] = data[key]
        form = build_form('%s_%s' % (node['id'], data['name']), form_data, rctx, where)
        condition = data.get('condition')
        if condition is not None:
            errors = validate_condition(condition, where + '.condition')
            rctx.errors.extend(errors)
        when = data.get('when')
        if when is not None:
            when = dict(when)
            operators = [op for op in WHEN_OPERATORS if op in when]
            if len(operators) != 1:
                rctx.error(where + '.when', _('"when" takes one of %s')
                           % ', '.join(WHEN_OPERATORS))
            if when['field'] not in placed:
                rctx.error(where + '.when.field', no_field(label, when['field'])
                           if when['field'] not in by_name else _(
                               '%r is not a field of an earlier step')
                           % (when['field'],))
            else:
                when['step'] = placed[when['field']]
        on_submit = pipeline.resolve_pipeline(
            rctx, data, where, event=pipeline.ON_SUBMIT,
            model=found.model if found is not None else None, exposure=found,
            form_fields=names, intermediate=True,
            where='%s.pipeline.%s' % (where, pipeline.ON_SUBMIT))
        if form is None:
            return None
        return WizardStepBuild(data['name'], data.get('title') or data['name'],
                               form, data.get('description', ''), condition, when,
                               on_submit)

    def preview(self, build, rctx):
        step = build.steps[0]
        form = step.form.get_form(prefix=step.name, preview=True)
        total = len(build.steps)
        wizard = {
            'title': build.title, 'step': step, 'number': 1, 'total': total,
            'percent': int(round(100 / total)), 'form': form, 'is_first': True,
            'is_last': total == 1, 'action_url': '#', 'step_field': 'wizard_step',
            'action_field': 'wizard_action', 'multipart': form.is_multipart(),
            'steps': [{'name': item.name, 'title': item.title, 'number': index + 1,
                       'done': False, 'current': index == 0, 'reachable': False}
                      for index, item in enumerate(build.steps)],
        }
        return render_to_string(TEMPLATE, {'b': build, 'wizard': wizard,
                                           'preview': True})

    def render(self, build, rctx, children):
        if build.model is None:
            return mark_safe('')
        if rctx.preview:
            return self.preview(build, rctx)
        request = rctx.request
        page = getattr(request, 'gtdesign_page', None)
        if page is None or endpoint_url(rctx, build) is None:
            return mark_safe('')
        if not can(rctx, build.perms[build.action]):
            return no_permission(build)
        parent = None
        if build.mode == 'edit':
            parent = getattr(request, 'gtdesign_parent', None)
            if parent is None or not site_allows(build, parent, request):
                return no_permission(build)
        view = DesignWizardView(build, request, page, parent)
        view.load_state()
        context = view.get_context_data()
        context.update({'b': build, 'preview': False})
        return render_to_string(TEMPLATE, context, request=request)

    def endpoints(self, build):
        if build.model is None:
            return []
        # The engine's PARENT_GROUP: it evaluates the node's conditions with
        # the object of the URL.
        suffix = r'(?P<parent_pk>[^/.]+)' if build.mode == 'edit' else ''
        return [Endpoint(suffix, WizardViewSet, 'gtdesign-%s' % build.id)]


WIZARD_COMPONENTS = [WizardComponent]
