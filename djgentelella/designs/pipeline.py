"""The pipeline of a design page: what happens before it is drawn and when one
of its forms is sent, declared in the document instead of written as a view.

A pipeline runs **steps**, Python functions the project registers with a
name (:func:`register_process` or the :func:`process` decorator), of three
kinds, always in this order:

``validation``
    adds errors to the form, per field or general
    (:meth:`PipelineContext.add_error` or a ``ValidationError``); one error
    stops the submission: nothing is computed or saved.
``computation``
    sets values of fields before the save (:meth:`PipelineContext.set_value`
    or a returned ``dict``): fields of the form, or others the step declares
    in the document (``writes``), never the version of optimistic locking.
``process``
    runs inside the transaction of the save, after it; an error rolls the
    save and every process back and is shown on the form.

Then the **branch**: the first of ``branches`` whose condition holds says
where to go (``page:<path>``, ``flow:<name>[:<transition>]``, a URL name or
a local path); one without a condition is the default and goes last.

In the document, a page has ``root.props.pipeline.before_render`` and a
component with a form (``object_management``, ``inline_object_management``,
``crud_classic``) ``props.pipeline.on_submit``::

    "pipeline": {"on_submit": {
        "steps": [
            {"name": "shop.check_stock"},
            {"name": "shop.order_total", "writes": ["total"]},
            {"name": "shop.take_stock",
             "condition": {"perm": "shop.add_order"}},
            {"name": "shop.notify", "params": {"group": "sales"}}],
        "branches": [{"to": "page:orders/review",
                      "condition": {"auth": "big_order"}},
                     {"to": "page:orders/done"}]}}

A step is called ``function(ctx, **params)``: ``ctx`` is a
:class:`PipelineContext` and ``params`` are the step's ``params``, validated
when the page is published against the JSON Schema the step declared. A
name that is not registered, bad params, a ``writes`` the model does not
allow or a branch that leads back to its own page are errors of the
document (:func:`resolve_pipeline`), never of a request.

Steps run as the user of the request: none of them is a way around the
permissions of the component, which are checked before the pipeline runs,
nor around ``Flow.run`` -- a branch to a flow opens its page, where the
transition checks its own permissions. A step is found only by its
registered name: the document never names an importable path.

:func:`run_pipeline` is the public entry point, for anything else that
sends a form (a wizard, a view of the project). See ``docs/source/pipeline.rst``.
"""

import inspect
import logging
import re
import threading
import traceback
from dataclasses import dataclass, field

from django import forms
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import router, transaction
from django.http import HttpResponseRedirect
from django.urls import NoReverseMatch, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _

from djgentelella.authorization import evaluate_condition, validate_condition
from djgentelella.designs.jsonschema import Error, validate
from djgentelella.designs.models import Page, normalize_path
from djgentelella.locking import VERSION_FIELD, version_field
from djgentelella.sites import get_current_site
from rest_framework.exceptions import ValidationError as APIValidationError

__all__ = [
    'BEFORE_RENDER', 'BranchBuild', 'KINDS', 'ON_SUBMIT', 'PAGE_PIPELINE_SCHEMA',
    'PIPELINE_SCHEMA', 'PipelineBuild', 'PipelineContext', 'PipelineResult',
    'PipelineFormMixin', 'PipelinePageMixin', 'PipelineViewSetMixin', 'Process',
    'STAGE_SCHEMA', 'StepBuild', 'before_render', 'build_pipeline', 'catalogue',
    'context_for_form', 'form_errors_to', 'generation', 'get_process', 'process',
    'register_process', 'registered_processes', 'resolve_branch_target',
    'resolve_pipeline', 'run_before_render', 'run_form_pipeline', 'run_pipeline',
    'run_serializer_pipeline', 'serializer_errors', 'step_build',
    'unregister_process',
]

logger = logging.getLogger('djgentelella.designs.pipeline')

#: The kinds of step, in the order they run.
KINDS = ('validation', 'computation', 'process')
#: The moments a pipeline runs at.
BEFORE_RENDER = 'before_render'
ON_SUBMIT = 'on_submit'
#: A step name: ``app.name`` (dots, letters, digits and ``_``).
NAME_PATTERN = r'^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$'
#: The params of a step that declares none.
NO_PARAMS = {'type': 'object', 'additionalProperties': False, 'properties': {}}
#: How many published pages a ``before_render`` redirect is followed through
#: when looking for a loop.
CYCLE_DEPTH = 8

CONDITION = {'x-widget': 'condition', 'title': 'Only when'}
STEP_SCHEMA = {
    'type': 'object',
    'required': ['name'],
    'additionalProperties': False,
    'properties': {
        'name': {'type': 'string', 'pattern': NAME_PATTERN,
                 'x-widget': 'pipeline-step', 'title': 'Registered step'},
        'kind': {'enum': list(KINDS),
                 'title': 'Its kind (optional; checked against the step)'},
        'params': {'type': 'object', 'x-widget': 'pipeline-params',
                   'title': 'Parameters (the schema of the step)'},
        'condition': CONDITION,
        'writes': {'type': 'array', 'items': {'type': 'string'},
                   'x-widget': 'model-fields',
                   'title': 'Fields outside the form a computation sets'},
    },
}
BRANCH_SCHEMA = {
    'type': 'object',
    'required': ['to'],
    'additionalProperties': False,
    'properties': {
        'to': {'type': 'string', 'minLength': 1, 'x-widget': 'branch-target',
               'title': '"page:<path>", "flow:<name>[:<transition>]", a URL '
                        'name or a local path'},
        'condition': CONDITION,
    },
}
STAGE_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'steps': {'type': 'array', 'items': STEP_SCHEMA,
                  'title': 'Validations, computations and processes'},
        'branches': {'type': 'array', 'items': BRANCH_SCHEMA,
                     'title': 'Where to go (the first that holds; the last '
                              'one without a condition is the default)'},
    },
}
#: The ``pipeline`` prop of a component with a form.
PIPELINE_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'x-widget': 'pipeline',
    'title': 'Pipeline when the form is sent',
    'properties': {ON_SUBMIT: STAGE_SCHEMA},
}
#: The ``pipeline`` prop of the page (the root).
PAGE_PIPELINE_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'x-widget': 'pipeline',
    'title': 'Pipeline before the page is drawn',
    'properties': {BEFORE_RENDER: STAGE_SCHEMA},
}


# -- the registry ------------------------------------------------------------------

@dataclass(frozen=True)
class Process:
    """A registered step."""

    name: str
    kind: str
    function: object
    #: JSON Schema of its ``params`` (:mod:`djgentelella.designs.jsonschema`).
    schema: dict = field(default_factory=lambda: dict(NO_PARAMS))
    label: str = ''
    description: str = ''
    #: The label of the installed app whose module defines the function
    #: (``''`` when none does).
    app: str = ''


def app_of(function):
    """The label of the installed app that defines ``function``, or ``''``."""
    module = getattr(function, '__module__', None) or ''
    found = apps.get_containing_app_config(module) if module else None
    return found.label if found is not None else ''


_registry = {}
_lock = threading.Lock()
_generation = [0]


def _bump():
    _generation[0] += 1


def generation():
    """A number that changes whenever a step is registered or removed: part of
    the key resolved pages are cached by."""
    return _generation[0]


def register_process(name, function=None, *, kind, schema=None, label='',
                     description=''):
    """Register ``function`` as the step ``name`` of ``kind`` (one of
    :data:`KINDS`); without ``function``, a decorator::

        register_process('shop.check_stock', check_stock, kind='validation')

        @register_process('shop.order_total', kind='computation')
        def order_total(ctx):
            ...

    ``name`` is ``app.name``. ``schema`` is the JSON Schema of the step's
    ``params`` (by default it takes none). Registering a name again replaces
    the step. Call it from a ``gtdesigns.py`` (imported when the project
    starts) or from an ``AppConfig.ready()``.
    """
    if not isinstance(name, str) or not re.match(NAME_PATTERN, name):
        raise ImproperlyConfigured('A pipeline step is named "app.name", not %r'
                                   % (name,))
    if kind not in KINDS:
        raise ImproperlyConfigured('The kind of step %r is one of %s, not %r'
                                   % (name, ', '.join(KINDS), kind))
    if schema is not None and not isinstance(schema, dict):
        raise ImproperlyConfigured('The schema of step %r is a dict' % (name,))

    def decorator(target):
        if not callable(target):
            raise ImproperlyConfigured('Step %r is not callable' % (name,))
        with _lock:
            _registry[name] = Process(
                name, kind, target, dict(schema) if schema else dict(NO_PARAMS),
                label or name, description or '', app_of(target))
            _bump()
        return target
    return decorator(function) if function is not None else decorator


def process(name, *, kind, schema=None, label='', description=''):
    """:func:`register_process` as a decorator::

        @process('shop.take_stock', kind='process')
        def take_stock(ctx):
            ...
    """
    return register_process(name, kind=kind, schema=schema, label=label,
                            description=description)


def unregister_process(name):
    with _lock:
        if _registry.pop(name, None) is not None:
            _bump()


def get_process(name):
    """The :class:`Process` registered as ``name``, or ``None``."""
    return _registry.get(name)


def registered_processes(kind=None):
    """``{name: Process}``, only those of ``kind`` when given."""
    return {name: found for name, found in sorted(_registry.items())
            if kind is None or found.kind == kind}


def catalogue():
    """The registered steps as data, for whoever writes documents
    (djgentelella-editor): ``[{name, kind, label, description, schema,
    app}]`` -- ``app``, the label of the app that defines the step."""
    return [{'name': found.name, 'kind': found.kind, 'label': str(found.label),
             'description': str(found.description), 'schema': found.schema,
             'app': found.app}
            for found in registered_processes().values()]


# -- the build -------------------------------------------------------------------

@dataclass
class StepBuild:
    name: str
    kind: str
    process: Process
    params: dict = field(default_factory=dict)
    condition: object = None
    #: Fields outside the form a computation may set.
    writes: tuple = ()


@dataclass
class BranchBuild:
    """Where a branch goes: exactly one of ``url``, ``url_name``, ``page`` or
    ``flow``. ``takes_pk``: the target is about the object that was saved."""

    to: str
    condition: object = None
    url: str = ''
    url_name: str = ''
    page: str = ''
    flow: str = ''
    transition: str = ''
    takes_pk: bool = False

    def url_for(self, obj=None):
        """The URL of the branch for the saved ``obj``, or ``None``."""
        pk = getattr(obj, 'pk', None)
        if self.takes_pk and pk is None:
            return None
        try:
            if self.url:
                return self.url
            if self.page:
                path = '%s/%s' % (self.page, pk) if self.takes_pk else self.page
                return reverse('gt-design-page', args=[path])
            if self.flow:
                if self.transition:
                    return reverse('flow_transition',
                                   args=[self.flow, self.transition, pk])
                return reverse('flow_detail', args=[self.flow, pk])
            if self.takes_pk:
                try:
                    return reverse(self.url_name, args=[pk])
                except NoReverseMatch:
                    return reverse(self.url_name, kwargs={'pk': pk})
            return reverse(self.url_name)
        except NoReverseMatch:
            logger.warning('Pipeline branch %r cannot be reversed', self.to)
            return None


@dataclass
class PipelineBuild:
    """The resolved pipeline of one moment (``before_render`` or
    ``on_submit``) of a page or a node."""

    event: str
    #: Sorted by kind (:data:`KINDS`), in document order within a kind.
    steps: list = field(default_factory=list)
    branches: list = field(default_factory=list)
    #: The model of the form, or ``None``.
    model: type = None

    def steps_of(self, kind):
        return [step for step in self.steps if step.kind == kind]

    def __bool__(self):
        return bool(self.steps or self.branches)


# -- resolve -------------------------------------------------------------------------

def _takes_kind(hook):
    try:
        parameters = inspect.signature(hook).parameters
    except (TypeError, ValueError):
        return False
    return 'kind' in parameters or any(
        item.kind == inspect.Parameter.VAR_KEYWORD for item in parameters.values())


def _find_process(rctx, name, path, kind=None):
    hook = getattr(rctx, 'pipeline_step', None)
    if hook is not None:
        # The kind of the document, to a hook that takes it (one that
        # generates the step knows it from there).
        if kind and _takes_kind(hook):
            return hook(name, path, kind=kind)
        return hook(name, path)
    found = get_process(name)
    if found is None:
        rctx.error(path, _('no pipeline step %r is registered') % (name,))
    return found


def step_build(name, kind, function, *, params=None, condition=None, writes=(),
               schema=None, label='', description=''):
    """A :class:`StepBuild` of ``function`` for code that builds a
    :class:`PipelineBuild` by hand (code generated from a design), without
    registering it. ``kind`` is one of :data:`KINDS`."""
    if kind not in KINDS:
        raise ImproperlyConfigured('The kind of step %r is one of %s, not %r'
                                   % (name, ', '.join(KINDS), kind))
    found = Process(name, kind, function, dict(schema or NO_PARAMS), label or name,
                    description, app_of(function))
    return StepBuild(name, kind, found, dict(params or {}), condition, tuple(writes))


def _check_writes(rctx, step, path, model, exposure, form_fields):
    """The fields a computation declares it sets outside the form."""
    writes = step.get('writes') or []
    if not writes:
        return ()
    if model is None:
        rctx.error(path, _('only a step of a form over a model can declare '
                           '"writes"'))
        return ()
    allowed = {model_field.name for model_field in exposure.model_fields()} \
        if exposure is not None else None
    try:
        locked = version_field(model)
    except ImproperlyConfigured:
        locked = None
    for name in writes:
        try:
            model_field = model._meta.get_field(name)
        except FieldDoesNotExist:
            model_field = None
        if model_field is None or (allowed is not None and name not in allowed):
            rctx.error(path, _('%(model)s has no field %(field)r a design may '
                               'use') % {'model': model._meta.label, 'field': name})
        elif name == locked:
            rctx.error(path, _('%r is the version of optimistic locking: no '
                               'step may set it') % (name,))
        elif not getattr(model_field, 'concrete', False) or model_field.many_to_many \
                or model_field.primary_key or not model_field.editable:
            rctx.error(path, _('%r is not a field a step can set') % (name,))
    if len(set(writes)) != len(writes):
        rctx.error(path, _('a field is listed twice'))
    return tuple(name for name in writes if name not in (form_fields or ()))


def _self_path(rctx):
    meta = rctx.design.get('meta') or {}
    url = meta.get('url')
    return normalize_path(url) if isinstance(url, str) else None


def _before_render_targets(document):
    """The ``page:`` paths the ``before_render`` branches of a document go to."""
    root = (document or {}).get('root') if isinstance(document, dict) else None
    props = (root or {}).get('props') if isinstance(root, dict) else None
    stage = (((props or {}).get('pipeline') or {}).get(BEFORE_RENDER) or {}) \
        if isinstance(props, dict) else {}
    targets = []
    for branch in (stage.get('branches') or []) if isinstance(stage, dict) else []:
        to = branch.get('to') if isinstance(branch, dict) else None
        if isinstance(to, str) and to.startswith('page:'):
            targets.append(normalize_path(to[len('page:'):]))
    return targets


def _leads_back(rctx, start, own):
    """Whether following the ``before_render`` branches of the published pages
    from ``start`` gets back to ``own``."""
    seen, frontier = set(), [start]
    for _depth in range(CYCLE_DEPTH):
        following = []
        for path in frontier:
            if path in seen:
                continue
            seen.add(path)
            page = Page.objects.find(path, rctx.site)
            if page is None:
                continue
            for target in _before_render_targets(page.document):
                if target == own:
                    return True
                following.append(target)
        if not following:
            return False
        frontier = following
    return False


def _resolve_branch(rctx, branch, path, event, model):
    to = branch['to']
    hook = getattr(rctx, 'branch_target', None)
    if hook is not None:
        found = hook(to, path + '.to', event=event, model=model)
    else:
        found = resolve_branch_target(rctx, to, path + '.to', event, model)
    if found is not None:
        found.condition = branch.get('condition')
    return found


def resolve_branch_target(rctx, to, path, event=ON_SUBMIT, model=None):
    """The :class:`BranchBuild` of the branch target ``to`` (without a
    condition), or ``None`` after reporting why at ``path`` (the path of
    ``to``): ``page:<path>`` (a published page, no ``before_render`` loop),
    ``flow:<name>[:<transition>]``, a local path or a URL name. What
    :meth:`ResolveContext.branch_target` answers by default."""
    condition = None
    path = path or '$.to'
    # The messages are reported at "<branch>.to".
    path = path[:-len('.to')] if path.endswith('.to') else path
    if to.startswith('page:'):
        target = normalize_path(to[len('page:'):])
        if not target:
            rctx.error(path + '.to', _('"page:" needs a path'))
            return None
        own = _self_path(rctx)
        if event == BEFORE_RENDER and own is not None and (
                target == own or _leads_back(rctx, target, own)):
            rctx.error(path + '.to', _('%r leads back to this page before it is '
                                       'drawn: a redirect loop') % (to,))
            return None
        if target == own:
            document = rctx.design
        else:
            page = Page.objects.find(target, rctx.site)
            if page is None:
                rctx.error(path + '.to', _('no design page %r is published')
                           % (target,))
                return None
            document = page.document if isinstance(page.document, dict) else {}
        parent = ((document.get('meta') or {}).get('parent') or {}).get('model')
        if parent:
            if model is None or not isinstance(parent, str) or \
                    parent.lower() != model._meta.label_lower:
                rctx.error(path + '.to', _('design page %(page)r is about one '
                                           '%(parent)s: a branch can only go '
                                           'there after saving one') % {
                    'page': target, 'parent': parent})
                return None
            return BranchBuild(to, condition, page=target, takes_pk=True)
        return BranchBuild(to, condition, page=target)
    if to.startswith('flow:'):
        if event != ON_SUBMIT or model is None:
            rctx.error(path + '.to', _('a branch to a flow needs the object a '
                                       'form saved'))
            return None
        found = rctx.row_link({'url_name': to, 'title': to}, model, path + '.to')
        if found is None:
            return None
        return BranchBuild(to, condition, flow=found.flow,
                           transition=found.transition, takes_pk=True)
    if to.startswith('/'):
        if not url_has_allowed_host_and_scheme(to, allowed_hosts=None):
            rctx.error(path + '.to', _('%r is not a local path') % (to,))
            return None
        return BranchBuild(to, condition, url=to)
    try:
        reverse(to)
    except NoReverseMatch:
        pass
    else:
        return BranchBuild(to, condition, url_name=to)
    if model is not None and event == ON_SUBMIT:
        for args, kwargs in (([1], {}), ([], {'pk': 1})):
            try:
                reverse(to, args=args, kwargs=kwargs)
            except NoReverseMatch:
                continue
            return BranchBuild(to, condition, url_name=to, takes_pk=True)
    rctx.error(path + '.to', _('%r is neither "page:<path>", "flow:<name>", a URL '
                               'name of the project nor a local path') % (to,))
    return None


def resolve_pipeline(rctx, props, path, *, event, model=None, exposure=None,
                     form_fields=None, intermediate=False, where=None):
    """The :class:`PipelineBuild` of ``props["pipeline"][event]``, ``None``
    without one, after reporting each problem with ``rctx.error()``.

    ``path`` is the node's (``$.root.children[0]``...). ``model`` and
    ``exposure`` are those of the form of a component; ``form_fields`` the
    names it has. Checked here, when the document is validated or
    published: each step is registered (``rctx.pipeline_step``), its params
    fit its schema, its condition is valid, ``writes`` only names fields the
    model lets a design use -- never the version of optimistic locking --;
    each branch target exists, a default branch goes last, and no
    ``before_render`` branch leads back to its own page.

    ``intermediate``: the pipeline of a step of a wizard, run before anything
    is saved -- only validations and computations; a process or a branch is
    an error. ``where`` is the path of the stage in the document when it
    is not ``<path>.props.pipeline.<event>`` (a step of a wizard).
    """
    pipeline = (props or {}).get('pipeline')
    if not isinstance(pipeline, dict):
        return None
    stage = pipeline.get(event)
    if not isinstance(stage, dict):
        return None
    where = where or '%s.props.pipeline.%s' % (path, event)
    build = PipelineBuild(event, model=model)
    errors_before = len(rctx.errors)
    steps = []
    for index, step in enumerate(stage.get('steps') or []):
        step_path = '%s.steps[%d]' % (where, index)
        found = _find_process(rctx, step['name'], step_path + '.name',
                              step.get('kind'))
        condition = step.get('condition')
        if condition is not None:
            rctx.errors.extend(validate_condition(condition, step_path + '.condition'))
        if found is None:
            continue
        if step.get('kind') and step['kind'] != found.kind:
            rctx.error(step_path + '.kind', _('%(name)r is a %(kind)s, not a '
                                              '%(said)s') % {
                'name': found.name, 'kind': found.kind, 'said': step['kind']})
            continue
        if intermediate and found.kind == 'process':
            rctx.error(step_path + '.name', _(
                '%r is a process: a step of a wizard saves nothing, so it only '
                'runs validations and computations (put the process in the '
                'pipeline of the wizard, which runs when it finishes)')
                % (found.name,))
            continue
        params = step.get('params') or {}
        rctx.errors.extend(validate(params, found.schema or NO_PARAMS,
                                    step_path + '.params'))
        writes = ()
        if step.get('writes'):
            if found.kind != 'computation':
                rctx.error(step_path + '.writes', _('only a computation sets '
                                                    'fields'))
            else:
                writes = _check_writes(rctx, step, step_path + '.writes', model,
                                       exposure, form_fields)
        steps.append(StepBuild(found.name, found.kind, found, dict(params),
                               condition, writes))
    build.steps = sorted(steps, key=lambda item: KINDS.index(item.kind))
    branches = stage.get('branches') or []
    if intermediate and branches:
        rctx.error(where + '.branches', _('a step of a wizard does not branch: '
                                          'only the wizard, when it finishes'))
        branches = []
    for index, branch in enumerate(branches):
        branch_path = '%s.branches[%d]' % (where, index)
        condition = branch.get('condition')
        if condition is None and index != len(branches) - 1:
            rctx.error(branch_path, _('only the last branch can go without a '
                                      'condition (the default): the ones after '
                                      'it would never be taken'))
        if condition is not None:
            errors = validate_condition(condition, branch_path + '.condition')
            if errors:
                rctx.errors.extend(errors)
                continue
        found = _resolve_branch(rctx, branch, branch_path, event, model)
        if found is not None:
            build.branches.append(found)
    if len(rctx.errors) > errors_before:
        return None
    return build or None


def build_pipeline(stage, *, model=None, event=ON_SUBMIT, form_fields=None,
                   site=None, intermediate=False):
    """The :class:`PipelineBuild` of ``stage`` -- the ``on_submit`` (or
    ``before_render``) object of a document: ``{"steps": [...], "branches":
    [...]}`` -- for code that is not a design page: a
    :class:`~djgentelella.wizard.views.GTWizardView`, a view of the project,
    code generated from a design::

        build_pipeline({'steps': [{'name': 'shop.order_total',
                                   'writes': ['total']}],
                        'branches': [{'to': 'order-list'}]}, model=Order)

    Checked as :func:`resolve_pipeline` checks a document (``model`` and
    ``form_fields`` as there; ``site`` the Site the ``page:`` targets are
    looked up in); any problem raises ``ImproperlyConfigured`` with every
    message. A :class:`PipelineBuild` is returned as it is, and an empty
    stage (or ``None``) gives ``None``.
    """
    if stage is None or isinstance(stage, PipelineBuild):
        return stage or None
    errors = validate(stage, STAGE_SCHEMA, '$')
    if errors:
        raise ImproperlyConfigured('; '.join('%s: %s' % (error.path, error.message)
                                             for error in errors))
    # The components module imports this one.
    from djgentelella.designs.components import (  # noqa: PLC0415 (circular)
        ResolveContext,
    )
    rctx = ResolveContext({}, site=site)
    found = resolve_pipeline(rctx, {'pipeline': {event: stage}}, '$', event=event,
                             model=model, form_fields=form_fields,
                             intermediate=intermediate)
    if rctx.errors:
        raise ImproperlyConfigured('; '.join('%s: %s' % (error.path, error.message)
                                             for error in rctx.errors))
    return found


# -- run ------------------------------------------------------------------------------

class PipelineError(Exception):
    """A step did something no step may do (set a field it did not declare,
    the version of optimistic locking): a bug of the step, audited."""


class _Rollback(Exception):
    pass


def _request_of(request):
    """The Django request behind a DRF one."""
    return getattr(request, '_request', request)


class PipelineContext:
    """What a step sees: ``ctx`` in ``function(ctx, **params)``.

    ``request``, ``site`` and ``user`` (the steps run as that user); ``page``
    (the :class:`~djgentelella.designs.models.Page`, ``None`` outside one)
    and ``node`` (the id of the component); ``event`` (``before_render`` or
    ``on_submit``); ``form`` (the form or serializer being sent, or
    ``None``); ``data`` (its cleaned data -- the values computed so far
    included); ``instance`` (the object being edited or, once saved, the one
    created; ``None`` before saving a new object through the API);
    ``parent`` (the object of a page about one); ``values`` (what the
    computations set); ``step`` (the :class:`StepBuild` running).
    """

    def __init__(self, request=None, *, event=ON_SUBMIT, page=None, node=None,
                 form=None, data=None, instance=None, parent=None, model=None,
                 fields=None, site=None, user=None):
        self.request = request
        django_request = _request_of(request)
        if site is None and django_request is not None:
            site = get_current_site(django_request)
        self.site = site
        self.user = user if user is not None else getattr(request, 'user', None)
        self.event = event
        self.page = page if page is not None else getattr(
            django_request, 'gtdesign_page', None)
        self.node = node
        self.form = form
        self.data = data if data is not None else {}
        self.instance = instance
        self.parent = parent if parent is not None else getattr(
            django_request, 'gtdesign_parent', None)
        self.model = model if model is not None else (
            type(instance) if instance is not None else None)
        #: Names of the fields of the form; ``None``: no form (any name).
        self.fields = None if fields is None else frozenset(fields)
        self.values = {}
        #: ``before_render``: what the page gets as ``pipeline`` in its context.
        self.context = {}
        self.errors = []
        self.redirect_to = None
        self.step = None
        self.failed = False

    # -- what a step calls

    def add_error(self, field_name, message):
        """An error of ``field_name`` (``None``: of the whole form)."""
        self.errors.append((field_name, str(message)))

    def set_value(self, field_name, value):
        """Set ``field_name`` to ``value`` before the save (a computation)."""
        if self.step is not None and self.step.kind != 'computation':
            raise PipelineError('only a computation sets values, not %s'
                                % self.step.name)
        self._check_writable(field_name)
        self.values[field_name] = value
        self.data[field_name] = value
        form = self.form
        if isinstance(form, forms.BaseModelForm) and self.model is not None:
            try:
                model_field = self.model._meta.get_field(field_name)
            except FieldDoesNotExist:
                return
            if getattr(model_field, 'concrete', False) and not model_field.many_to_many:
                setattr(form.instance, model_field.name, value)

    def add_context(self, **values):
        """Values the page gets in its context, as ``pipeline.<name>``."""
        self.context.update(values)

    def redirect(self, url):
        """Go to ``url`` (a local one) instead of the branches."""
        if not isinstance(url, str) or not url_has_allowed_host_and_scheme(
                url, allowed_hosts=None):
            raise PipelineError('a step can only redirect to a local URL')
        self.redirect_to = url

    @property
    def has_errors(self):
        return bool(self.errors)

    def _check_writable(self, field_name):
        if field_name in ('pk', VERSION_FIELD):
            raise PipelineError('no step sets %r' % (field_name,))
        if self.model is not None:
            if field_name == self.model._meta.pk.name:
                raise PipelineError('no step sets the primary key')
            if field_name == version_field(self.model):
                raise PipelineError('%r is the version of optimistic locking: no '
                                    'step sets it' % (field_name,))
        if self.fields is None:
            return
        declared = self.step.writes if self.step is not None else ()
        if field_name not in self.fields and field_name not in declared:
            raise PipelineError('%r is neither a field of the form nor one the '
                                'step declares in "writes"' % (field_name,))


@dataclass
class PipelineResult:
    """What :func:`run_pipeline` did."""

    #: ``[(field or None, message)]``; empty when the pipeline went through.
    errors: list = field(default_factory=list)
    #: Where to go now (the branch taken, or a step's redirect), or ``None``.
    url: str = None
    values: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    #: Whether the object was saved (and the processes committed).
    saved: bool = False
    #: Whether a step failed with an unexpected error (logged).
    failed: bool = False

    @property
    def ok(self):
        return not self.errors

    def field_errors(self):
        result = {}
        for name, message in self.errors:
            if name is not None:
                result.setdefault(name, []).append(message)
        return result

    def general_errors(self):
        return [message for name, message in self.errors if name is None]


def _audit(ctx, step, exc, refused=False):
    """Log a failed step: names and code locations, never the data sent."""
    user = getattr(ctx.user, 'pk', None)
    page = getattr(ctx.page, 'path', None)
    if refused:
        errors = exc.error_list if hasattr(exc, 'error_list') else [
            error for items in exc.error_dict.values() for error in items]
        codes = sorted({error.code or '' for error in errors})
        logger.warning('Pipeline step %s (%s) refused the %s of page %s, node %s, '
                       'user %s (codes: %s)', step.name, step.kind, ctx.event, page,
                       ctx.node, user, ', '.join(codes) or '-')
        return
    logger.error('Pipeline step %s (%s) failed on the %s of page %s, node %s, '
                 'user %s: %s\n%s', step.name, step.kind, ctx.event, page, ctx.node,
                 user, type(exc).__name__,
                 ''.join(traceback.format_tb(exc.__traceback__)).rstrip())


def _add_validation_error(ctx, exc):
    if hasattr(exc, 'error_dict'):
        for name, errors in exc.error_dict.items():
            target = None if name == '__all__' else name
            for error in errors:
                for message in error.messages:
                    ctx.add_error(target, message)
    else:
        for message in exc.messages:
            ctx.add_error(None, message)


def _run_step(ctx, step):
    obj = ctx.instance if ctx.instance is not None else ctx.parent
    if step.condition is not None and not evaluate_condition(
            step.condition, _request_of(ctx.request), obj):
        return
    ctx.step = step
    try:
        returned = step.process.function(ctx, **step.params)
        if step.kind == 'computation' and isinstance(returned, dict):
            for name, value in returned.items():
                ctx.set_value(name, value)
    except ValidationError as exc:
        if step.kind == 'process':
            _audit(ctx, step, exc, refused=True)
        _add_validation_error(ctx, exc)
    except Exception as exc:  # noqa: BLE001 -- any failure of a step is audited
        _audit(ctx, step, exc)
        ctx.failed = True
        ctx.add_error(None, _('%(step)s could not be completed: nothing was saved.')
                      % {'step': step.process.label})
    finally:
        ctx.step = None


def _branch_url(pipeline, ctx):
    obj = ctx.instance if ctx.instance is not None else ctx.parent
    request = _request_of(ctx.request)
    for branch in pipeline.branches:
        if branch.condition is not None and not evaluate_condition(
                branch.condition, request, obj):
            continue
        return branch.url_for(ctx.instance)
    return None


def run_pipeline(pipeline, ctx, *, save=None, using=None):
    """Run ``pipeline`` (a :class:`PipelineBuild`, or ``None``: only the
    save) with ``ctx`` and return a :class:`PipelineResult`.

    1. validations, all of them; with errors it stops here;
    2. computations, which set ``ctx.data`` (and the instance of a model form);
    3. in one ``transaction.atomic(using=using)``: ``save(ctx)`` -- the
       caller's save, which returns the saved object -- and the processes;
       any error rolls all of it back;
    4. the branch: the first whose condition holds for the saved object.

    A step that raises ``ValidationError`` adds its messages as errors; any
    other exception is logged (the step, the page, the node, the user and
    where it failed, never the data) and becomes a general error. Errors are
    returned, not raised: the caller shows them its own way
    (:func:`form_errors_to`, :func:`serializer_errors`).
    """
    steps = pipeline.steps if pipeline is not None else []
    result = PipelineResult()
    for kind in ('validation', 'computation'):
        for step in steps:
            if step.kind == kind:
                _run_step(ctx, step)
        if ctx.errors:
            return _result(result, ctx)
    if using is None and ctx.model is not None:
        using = router.db_for_write(ctx.model)
    instance = ctx.instance
    adding = instance is None or getattr(instance._state, 'adding', False)
    try:
        with transaction.atomic(using=using):
            if save is not None:
                saved = save(ctx)
                if saved is not None:
                    ctx.instance = saved
            for step in steps:
                if step.kind == 'process':
                    _run_step(ctx, step)
                    if ctx.errors:
                        raise _Rollback()
    except _Rollback:
        if adding and ctx.instance is not None:
            # The row is gone with the transaction: the object is new again.
            ctx.instance.pk = None
            ctx.instance._state.adding = True
        return _result(result, ctx)
    result.saved = save is not None
    if ctx.redirect_to is None and pipeline is not None:
        result.url = _branch_url(pipeline, ctx)
    else:
        result.url = ctx.redirect_to
    return _result(result, ctx)


def _result(result, ctx):
    result.errors = list(ctx.errors)
    result.values = dict(ctx.values)
    result.context = dict(ctx.context)
    result.failed = ctx.failed
    return result


# -- what the components and the page view call ---------------------------------

def context_for_form(form, request, *, node=None, event=ON_SUBMIT, page=None,
                     fields=None):
    """A :class:`PipelineContext` for a (model) form already valid: its
    ``cleaned_data``, its instance and its fields."""
    instance = getattr(form, 'instance', None)
    return PipelineContext(
        request, event=event, page=page, node=node, form=form,
        data=form.cleaned_data, instance=instance,
        model=type(instance) if instance is not None else None,
        fields=list(form.fields) if fields is None else fields)


def form_errors_to(form, result):
    """Put the errors of ``result`` on ``form`` (a field it does not have
    becomes a general error)."""
    for name, message in result.errors:
        if name is not None and name in form.fields:
            form.add_error(name, message)
        elif name is not None:
            form.add_error(None, '%s: %s' % (name, message))
        else:
            form.add_error(None, message)


def serializer_errors(result):
    """The errors of ``result`` as the body of a 400 of the API:
    ``{field: [messages]}`` and the general ones joined in ``detail``."""
    body = result.field_errors()
    general = result.general_errors()
    if general:
        body['detail'] = ' '.join(general)
    return body


def before_render(resolved, request, *, page=None, parent=None):
    """Run the ``before_render`` pipeline of a resolved page for ``request``:
    the :class:`PipelineResult`, or ``None`` when the page has none.

    What the page view (:func:`djgentelella.designs.views.design_page`) does
    with it: errors refuse the page (403), a ``url`` redirects, and the
    ``context`` and ``values`` go to the template as ``pipeline``.
    """
    pipeline = getattr(resolved.root.build, 'pipeline', None)
    if not pipeline or resolved.preview:
        return None
    ctx = PipelineContext(request, event=BEFORE_RENDER, page=page,
                          node=resolved.root.id, parent=parent)
    return run_pipeline(pipeline, ctx)


# -- for code: views, viewsets and pages outside the design engine -----------------

def run_form_pipeline(pipeline, form, request, save, *, node=None, fields=None,
                      page=None):
    """Run ``pipeline`` for a valid ``form`` (:func:`context_for_form`):
    ``save(ctx)`` saves and returns the object. Its errors are put on the
    form (:func:`form_errors_to`); the :class:`PipelineResult` is returned
    -- ``result.url`` is the branch taken. What the ``crud_classic`` pages
    do, for a view of generated code."""
    ctx = context_for_form(form, request, node=node, page=page, fields=fields)
    result = run_pipeline(pipeline, ctx, save=save)
    if not result.ok:
        form_errors_to(form, result)
    return result


def run_serializer_pipeline(pipeline, serializer, request, save, *, node=None,
                            model=None, fields=None):
    """Run ``pipeline`` for a valid DRF ``serializer``: ``save()`` (no
    arguments) saves it. Its errors raise the 400 of the API
    (:func:`serializer_errors`); the :class:`PipelineResult` is returned
    otherwise. What ``object_management`` does in ``perform_create`` and
    ``perform_update``."""
    meta = getattr(serializer, 'Meta', None)
    model = model or getattr(meta, 'model', None)
    if fields is None:
        fields = [name for name, item in serializer.fields.items()
                  if not item.read_only]
    ctx = PipelineContext(request, node=node, form=serializer,
                          data=serializer.validated_data,
                          instance=serializer.instance, model=model, fields=fields)

    def do_save(ctx):
        save()
        return serializer.instance

    result = run_pipeline(pipeline, ctx, save=do_save)
    if not result.ok:
        raise APIValidationError(serializer_errors(result))
    return result


def run_before_render(pipeline, request, *, page=None, parent=None, node=None):
    """Run a ``before_render`` ``pipeline`` for ``request`` in a view that is
    not a design page: the :class:`PipelineResult` (errors refuse the page,
    ``url`` redirects, ``values`` and ``context`` go to the template)."""
    ctx = PipelineContext(request, event=BEFORE_RENDER, page=page, node=node,
                          parent=parent)
    return run_pipeline(pipeline, ctx)


def _built(view, stage, event=ON_SUBMIT, form_fields=None):
    if not stage:
        return None
    return build_pipeline(stage, model=getattr(view, 'model', None), event=event,
                          form_fields=form_fields)


class PipelineFormMixin:
    """A ``CreateView``/``UpdateView`` (or a ``CRUDView`` mixin) whose save
    goes through :attr:`pipeline`, an ``on_submit`` stage or a
    :class:`PipelineBuild`: its errors show on the form, nothing saved; its
    branch is where it goes after saving."""

    pipeline = None
    pipeline_node = None

    def get_pipeline(self, form=None):
        return _built(self, self.pipeline,
                      form_fields=list(form.fields) if form is not None else None)

    def form_valid(self, form):
        found = self.get_pipeline(form)
        if not found:
            return super().form_valid(form)
        adding = getattr(getattr(form, 'instance', None), 'pk', None) is None
        responses = []

        def save(ctx):
            responses.append(super(PipelineFormMixin, self).form_valid(form))
            return getattr(self, 'object', None)

        result = run_form_pipeline(found, form, self.request, save,
                                   node=self.pipeline_node)
        if not result.ok:
            if adding:
                self.object = None
            return self.form_invalid(form)
        if result.url:
            return HttpResponseRedirect(result.url)
        return responses[0]


class PipelineViewSetMixin:
    """A DRF viewset (``ModelViewSet``, an ``ObjectManagement``) whose
    ``perform_create``/``perform_update`` go through :attr:`pipeline`: its
    errors are a 400; its branch comes in the response as
    ``gtdesign_redirect``, which the ``gtdesign_pipeline_events()`` of
    ``designs/data_components.js`` follows."""

    pipeline = None
    pipeline_node = None
    pipeline_redirect = None

    def get_pipeline(self, serializer=None):
        fields = None
        if serializer is not None:
            fields = [name for name, item in serializer.fields.items()
                      if not item.read_only]
        return _built(self, self.pipeline, form_fields=fields)

    def pipeline_save(self, serializer, save):
        found = self.get_pipeline(serializer)
        if not found:
            save()
            return None
        result = run_serializer_pipeline(found, serializer, self.request, save,
                                         node=self.pipeline_node,
                                         model=getattr(self, 'model', None))
        self.pipeline_redirect = result.url
        return result

    def perform_create(self, serializer):
        self.pipeline_save(serializer, lambda: super(
            PipelineViewSetMixin, self).perform_create(serializer))

    def perform_update(self, serializer):
        self.pipeline_save(serializer, lambda: super(
            PipelineViewSetMixin, self).perform_update(serializer))

    def finalize_response(self, request, response, *args, **kwargs):
        if self.pipeline_redirect and isinstance(getattr(response, 'data', None),
                                                 dict):
            response.data['gtdesign_redirect'] = self.pipeline_redirect
        return super().finalize_response(request, response, *args, **kwargs)


class PipelinePageMixin:
    """A view whose ``GET`` runs :attr:`pipeline`, a ``before_render`` stage
    (or :class:`PipelineBuild`), first: errors refuse it (403), a branch
    redirects, and the computed values and ``add_context`` reach the template
    as ``pipeline`` -- what a design page does."""

    pipeline = None
    pipeline_node = None

    def get_pipeline(self):
        return _built(self, self.pipeline, event=BEFORE_RENDER)

    def get(self, request, *args, **kwargs):
        found = self.get_pipeline()
        self.pipeline_result = None
        if found:
            result = run_before_render(found, request, node=self.pipeline_node)
            if not result.ok:
                raise PermissionDenied(' '.join(message for _field, message
                                                in result.errors))
            if result.url:
                return HttpResponseRedirect(result.url)
            self.pipeline_result = result
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result = getattr(self, 'pipeline_result', None)
        if result is not None:
            context['pipeline'] = {**result.values, **result.context}
        return context
