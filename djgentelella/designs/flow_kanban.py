"""``flow_kanban``: the objects of a flow as cards, one column per state.

Moving a card to another column runs a transition of the flow, through its
public API (:meth:`~djgentelella.flows.base.Flow.check` and
:meth:`~djgentelella.flows.base.Flow.run`): with its permissions, its
condition and its form, logged in ``FlowTransitionLog`` like any other run.
The board never changes a state by itself.

Props (validated when the document is resolved: a flow or a state that does
not exist is an error of the document):

``flow``         the flow's name (``app.Flow``); its model must be exposed
``states``       the columns and their order; by default the activities of the
                 flow an object can wait in (not switches, actions nor joins)
``title_field``  the card's title; by default ``str(object)``
``fields``       the fields shown on each card (those the exposure allows)
``ordering``     the order of the cards in a column (``-pk`` by default)
``limit``        a visual limit per column: past it the column is marked
``page_size``    cards per column on load and on each "load more" (20)
``site_field``   a foreign key of the model to ``sites.Site``: only the
                 objects of the current Site and the global ones are shown

The board shows only what ``Flow.get_queryset(user)`` lets the user reach,
of the current Site: an object whose flow instance belongs to another Site is
left out, and so is, with ``site_field``, an object of another Site.

Its endpoint (``gtapis/designs/<page>/<node>/``) answers

* ``GET cards/?state=<s>&offset=<n>`` -- the next cards of a column;
* ``GET <pk>/transitions/?target=<s>`` -- the transitions that take the
  object from its state to ``<s>``, those the user may run now and the others
  with the reason why not;
* ``GET <pk>/form/?transition=<t>`` -- the transition's form, for the modal;
* ``POST <pk>/move/`` -- runs ``transition`` (with its form fields, prefix
  ``flow``, and ``comment``); 403 with ``detail`` when the flow refuses it,
  400 with the form when it is not valid.
"""

from dataclasses import dataclass, field

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Count, Exists, F, OuterRef, Q, Window
from django.db.models.functions import RowNumber
from django.http import Http404
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from djgentelella.designs.builds import DataBuild
from djgentelella.designs.components import Endpoint, RuntimeComponent
from djgentelella.designs.data_components import (
    NOT_LISTABLE, allowed_fields, data_build, endpoint_url, flows_installed,
    json_config, kind_of, label, no_permission, sample_value,
)
from djgentelella.sites import get_current_site, site_q

__all__ = ['FLOW_KANBAN_COMPONENTS', 'FlowKanbanBuild', 'FlowKanbanComponent',
           'FlowKanbanViewSet', 'TEMPLATE', 'TRANSIENT', 'board', 'board_queryset',
           'card', 'kanban_config', 'kanban_flow', 'kanban_messages',
           'kanban_page_context', 'moves_for', 'render_cards', 'resting_states']

SCRIPT = 'gentelella/js/designs/flow_kanban.js'
#: The board's template; :func:`kanban_page_context` is its context.
TEMPLATE = 'gtdesigns/components/flow_kanban.html'
STYLE = 'gentelella/css/flow_kanban.css'
#: Activities an object never waits in: they move on as soon as entered.
TRANSIENT = ('switch', 'action', 'join')
PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
#: The prefix of a transition's form in the modal, as on the flow pages.
FORM_PREFIX = 'flow'


@dataclass
class FlowKanbanBuild(DataBuild):
    """A board of the objects of one flow, one column per state."""

    #: The flow's name; the flow itself is looked up for the Site of each
    #: request (``get_flow(name, site=...)``), as the flow pages do.
    flow: str = ''
    model: type = None
    states: list = field(default_factory=list)
    #: ``{state: label}`` of the flow it was resolved with, for the preview.
    labels: dict = field(default_factory=dict)
    title_field: str = ''
    fields: list = field(default_factory=list)
    ordering: list = field(default_factory=list)
    limit: int = None
    page_size: int = PAGE_SIZE
    site_field: str = ''
    #: Relations of the card's fields, read with the cards (no query per card).
    select_related: list = field(default_factory=list)


def resting_states(flow):
    """The activities of ``flow`` an object can wait in, in its order."""
    return [key for key, activity in flow.activities.items()
            if activity.type not in TRANSIENT]


def kanban_flow(build, request):
    """The flow of the board for the Site of ``request``, or ``None``."""
    # Optional app: only importable when it is installed (the build has a
    # flow only then).
    from djgentelella.flows.base import get_flow  # noqa: PLC0415
    return get_flow(build.flow, site=get_current_site(request))


def board_queryset(flow, build, request):
    """The objects of the board: ``flow.get_queryset(user)``, of the current
    Site, in the board's states, annotated with ``flow_state``."""
    # Optional app (see kanban_flow).
    from djgentelella.flows.models import FlowInstance  # noqa: PLC0415
    site = get_current_site(request)
    queryset = flow.get_queryset(request.user)
    # An object whose instance runs in another Site is not on this board.
    elsewhere = FlowInstance.objects.filter(
        flow=flow.name, content_type=flow.content_type(),
        object_id=OuterRef('flow_key')).exclude(site_q(site))
    queryset = queryset.filter(~Exists(elsewhere))
    if build.site_field:
        queryset = queryset.filter(site_q(site, field=build.site_field))
    if build.select_related:
        queryset = queryset.select_related(*build.select_related)
    return queryset.filter(flow_state__in=build.states)


def card_ordering(build):
    """The ordering of a column, with the pk last so pages never overlap."""
    ordering = list(build.ordering)
    if not any(name.lstrip('-') in ('pk', build.model._meta.pk.name)
               for name in ordering):
        ordering.append('-pk')
    return ordering


def order_expressions(ordering):
    return [F(name[1:]).desc() if name.startswith('-') else F(name).asc()
            for name in ordering]


def moves_for(flow, build, user):
    """``{state: [(target, label), ...]}``: the columns a card of each state
    may be moved to by ``user``, from the flow's graph and the user's
    permissions. Conditions need the object: they are checked on the move."""
    moves = {}
    order = {name: index for index, name in enumerate(build.states)}
    for state in build.states:
        targets = []
        for transition in flow.transitions:
            target = transition.target
            if (transition.auto or target == state or target not in build.states
                    or target in targets or not flow.leaves(transition, state)
                    or not flow.may_attempt(transition, user)):
                continue
            targets.append(target)
        moves[state] = [(target, str(flow.state_label(target)))
                        for target in sorted(targets, key=order.get)]
    return moves


def field_value(obj, model_field):
    if model_field.choices:
        return getattr(obj, 'get_%s_display' % model_field.name)()
    value = getattr(obj, model_field.name)
    if isinstance(value, bool):
        return _('Yes') if value else _('No')
    return value


def detail_url(flow, obj):
    try:
        return reverse('flow_detail', args=[flow.name, obj.pk])
    except NoReverseMatch:  # the project did not include djgentelella's URLs
        return ''


def card(flow, build, obj, moves):
    """What the card template shows of ``obj`` (annotated by the board)."""
    # Optional app (see kanban_flow).
    from djgentelella.flows.base import COMPLETED, LIVE, RUNNING  # noqa: PLC0415
    from djgentelella.flows.models import FlowInstance  # noqa: PLC0415
    meta = build.model._meta
    title = (field_value(obj, meta.get_field(build.title_field))
             if build.title_field else obj)
    state = obj.flow_state
    return {
        'pk': obj.pk, 'state': state, 'title': title,
        'status': obj.flow_status, 'movable': obj.flow_status in LIVE,
        # Only what is not the usual: an error, suspended, terminated.
        'status_label': ('' if obj.flow_status in (RUNNING, COMPLETED) else
                         dict(FlowInstance.STATUSES).get(obj.flow_status, '')),
        'fields': [(label(meta.get_field(name).verbose_name),
                    field_value(obj, meta.get_field(name)))
                   for name in build.fields],
        'url': detail_url(flow, obj),
        'targets': moves.get(state, []),
    }


def render_cards(cards, build):
    """The HTML of ``cards`` (dicts of :func:`card`) in a column of ``build``."""
    return render_to_string('gtdesigns/components/flow_kanban_cards.html',
                            {'cards': cards, 'b': build})


def first_cards(queryset, build):
    """The first page of every column, in one query: the cards numbered per
    state by a window function."""
    ordering = order_expressions(card_ordering(build))
    numbered = queryset.annotate(gtkanban_row=Window(
        RowNumber(), partition_by=[F('flow_state')], order_by=ordering))
    return numbered.filter(gtkanban_row__lte=build.page_size).order_by(
        *card_ordering(build))


def board(flow, build, request):
    """The columns of the board for ``request``: two queries, whatever the
    number of cards -- the counts per state and the first page of each."""
    queryset = board_queryset(flow, build, request)
    counts = dict(queryset.order_by().values_list('flow_state').annotate(
        total=Count('pk')).values_list('flow_state', 'total'))
    moves = moves_for(flow, build, request.user)
    by_state = {state: [] for state in build.states}
    for obj in first_cards(queryset, build):
        by_state[obj.flow_state].append(card(flow, build, obj, moves))
    columns = []
    for state in build.states:
        total = counts.get(state, 0)
        columns.append({
            'state': state, 'label': flow.state_label(state), 'total': total,
            'cards': by_state[state], 'has_more': total > len(by_state[state]),
            'over': build.limit is not None and total > build.limit,
        })
    return columns, moves


def kanban_messages():
    """The texts flow_kanban.js shows, in the language of the request."""
    return {
        'choose': _('Which transition?'),
        'error': _('The card could not be moved.'),
        'moved': _('Moved to %(state)s.'),
        'stopped': _('Moved, but the flow stopped on an error: %(error)s'),
    }


def kanban_config(build, flow, moves, url):
    """The configuration flow_kanban.js reads (``data-gtconfig``) of the
    board of ``build``, with ``url`` its endpoint (``FlowKanbanViewSet``)."""
    return {
        'id': build.id,
        'urls': {'base': url},
        'states': build.states,
        'labels': {state: str(flow.state_label(state)) for state in build.states},
        'moves': {state: [target for target, _label in targets]
                  for state, targets in moves.items()},
        'limit': build.limit,
        'page_size': build.page_size,
        'messages': kanban_messages(),
    }


def kanban_page_context(build, request, url):
    """What :data:`TEMPLATE` needs to draw the board of ``build`` for
    ``request``: ``{'b', 'columns', 'config'}``, with ``url`` the URL of
    its endpoint -- a :class:`FlowKanbanViewSet` serving ``build``.

    No published :class:`~djgentelella.designs.models.Page` is needed: code
    generated from a design (djgentelella-editor) calls it with its own
    build and URL. ``None`` when ``request`` may not see the board: no
    authenticated user, no such flow for the Site of the request, or a
    version of the flow without one of the columns.
    """
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated or not url:
        return None
    flow = kanban_flow(build, request)
    if flow is None or any(state not in flow.activities for state in build.states):
        return None
    columns, moves = board(flow, build, request)
    for column in columns:
        column['html'] = render_cards(column['cards'], build)
    return {'b': build, 'columns': columns,
            'config': json_config(build.id + '_gtconfig',
                                  kanban_config(build, flow, moves, url))}


class FlowKanbanComponent(RuntimeComponent):
    """The objects of a flow as cards in columns, one per state; dragging a
    card (or its "move to" menu) runs the flow's transition."""

    type = 'flow_kanban'
    label = gettext_lazy('Flow kanban (cards by state)')
    icon = 'fa fa-columns'
    props_schema = {
        'type': 'object',
        'required': ['flow'],
        'additionalProperties': False,
        'properties': {
            'flow': {'type': 'string', 'minLength': 1, 'x-widget': 'flow',
                     'title': 'Flow'},
            'title': {'type': 'string', 'title': 'Title'},
            'states': {'type': 'array', 'minItems': 1,
                       'items': {'type': 'string', 'minLength': 1},
                       'x-widget': 'flow-states',
                       'title': 'Columns: the states and their order '
                                '(empty = those of the flow)'},
            'title_field': {'type': 'string', 'x-widget': 'model-field',
                            'title': 'Card title (empty = the object)'},
            'fields': {'type': 'array', 'items': {'type': 'string'},
                       'x-widget': 'model-fields', 'title': 'Card fields'},
            'ordering': {'type': 'array', 'items': {'type': 'string'},
                         'title': 'Order of the cards (e.g. -pk)'},
            'limit': {'type': 'integer', 'minimum': 1,
                      'title': 'Cards per column before it is marked '
                               '(visual only)'},
            'page_size': {'type': 'integer', 'minimum': 1,
                          'maximum': MAX_PAGE_SIZE,
                          'title': 'Cards per column and per "load more"'},
            'site_field': {'type': 'string', 'x-widget': 'model-field',
                           'title': 'Foreign key to the Site (only the current '
                                    "Site's objects)"},
        },
    }

    def resolve(self, node, rctx, path):
        props = node.get('props') or {}
        build = data_build(FlowKanbanBuild, node, rctx)
        where = path + '.props.flow'
        if not flows_installed():
            rctx.error(where, _('flow_kanban needs djgentelella.flows in '
                                'INSTALLED_APPS'))
            return build
        flow = rctx.flow(props['flow'], where)
        if flow is None:
            return build
        found = rctx.exposure(flow.model._meta.label, where)
        if found is None:
            return build
        model = found.model
        by_name = allowed_fields(found)

        states = props.get('states') or resting_states(flow)
        seen = set()
        for index, state in enumerate(states):
            at = '%s.props.states[%d]' % (path, index)
            if state not in flow.activities:
                rctx.error(at, _('flow %(flow)r has no state %(state)r') % {
                    'flow': flow.name, 'state': state})
            elif state in seen:
                rctx.error(at, _('state %r is repeated') % (state,))
            seen.add(state)

        def card_field(name, at):
            if name not in by_name:
                rctx.error(at, _('%(field)r is not a field of %(model)s the '
                                 'design may show') % {'field': name,
                                                       'model': model._meta.label})
                return False
            kind = kind_of(by_name[name])
            if kind in NOT_LISTABLE or kind == 'm2m':
                rctx.error(at, _('%r cannot be shown on a card') % (name,))
                return False
            return True

        select_related = []
        names = list(props.get('fields') or [])
        title_field = props.get('title_field') or ''
        for name, at in ([(title_field, path + '.props.title_field')]
                         if title_field else []) + [
                (name, '%s.props.fields[%d]' % (path, index))
                for index, name in enumerate(names)]:
            if card_field(name, at) and by_name[name].is_relation \
                    and name not in select_related:
                rctx.exposure(by_name[name].related_model._meta.label, at)
                select_related.append(name)

        ordering = props.get('ordering') or ['-pk']
        for index, name in enumerate(ordering):
            bare = name.lstrip('-')
            if bare not in ('pk', 'flow_due_at') and (
                    bare not in by_name or kind_of(by_name[bare]) == 'm2m'):
                rctx.error('%s.props.ordering[%d]' % (path, index),
                           _('unknown field %r') % (name,))

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
        if rctx.has_errors_under(path):
            return build
        build.title = props.get('title') or str(flow)
        build.flow = flow.name
        build.model = model
        build.states = list(states)
        build.labels = {state: flow.state_label(state) for state in states}
        build.title_field = title_field
        build.fields = names
        build.ordering = list(ordering)
        build.limit = props.get('limit')
        build.page_size = props.get('page_size') or PAGE_SIZE
        build.site_field = site_field
        build.select_related = select_related
        return build

    def render(self, build, rctx, children):
        if build.model is None:
            return mark_safe('')
        if rctx.preview:
            return self.render_preview(build, rctx)
        if rctx.user is None or not rctx.user.is_authenticated:
            return no_permission(build)
        context = kanban_page_context(build, rctx.request, endpoint_url(rctx, build))
        if context is None:
            return no_permission(build)
        return render_to_string(TEMPLATE, context, request=rctx.request)

    def render_preview(self, build, rctx):
        """The editor's preview: the columns, with sample cards; no row is
        read."""
        meta = build.model._meta
        columns = []
        for index, state in enumerate(build.states):
            columns.append({
                'state': state, 'label': build.labels.get(state, state),
                'total': 1, 'html': render_cards([{
                    'pk': index, 'state': state, 'movable': False, 'targets': [],
                    'title': '%s %d' % (label(meta.verbose_name), index + 1),
                    'fields': [(label(meta.get_field(name).verbose_name),
                                sample_value(meta.get_field(name), index + 1))
                               for name in build.fields],
                }], build)})
        return render_to_string(TEMPLATE, {
            'b': build, 'columns': columns, 'preview': True})

    def media(self, build, rctx):
        return {'js': [SCRIPT], 'css': [STYLE]}

    def endpoints(self, build):
        if build.model is None:
            return []
        return [Endpoint('', FlowKanbanViewSet, 'gtdesign-%s' % build.id)]


class CommentForm(forms.Form):
    comment = forms.CharField(label=gettext_lazy('Comment'), required=False,
                              widget=forms.Textarea(attrs={'rows': 2,
                                                           'class': 'form-control'}))


class FlowKanbanViewSet(viewsets.ViewSet):
    """The endpoint of one ``flow_kanban`` node: the build :meth:`get_build`
    answers. Every object is looked up in :func:`board_queryset`; anything
    outside it is a 404."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    renderer_classes = (JSONRenderer,)
    #: The board this viewset serves; ``None``: the one of the design page
    #: the request comes through (``request.gtdesign_build``).
    kanban_build = None

    def get_build(self):
        """The :class:`FlowKanbanBuild` served: :attr:`kanban_build` -- what
        a subclass outside the design engine sets, as code generated by
        djgentelella-editor does -- or else ``request.gtdesign_build``,
        which the engine's endpoint sets."""
        if self.kanban_build is not None:
            return self.kanban_build
        build = getattr(self.request, 'gtdesign_build', None)
        if build is None:
            raise Http404()
        return build

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.build = self.get_build()
        self.flow = kanban_flow(self.build, request)
        if self.flow is None or self.build.preview:
            raise Http404()

    def queryset(self):
        return board_queryset(self.flow, self.build, self.request)

    def get_object(self, pk):
        try:
            key = self.build.model._meta.pk.to_python(pk)
        except (ValidationError, ValueError):
            raise Http404() from None
        obj = self.queryset().filter(pk=key).first()
        if obj is None:
            raise Http404()
        return obj

    def card_html(self, obj):
        moves = moves_for(self.flow, self.build, self.request.user)
        return render_cards([card(self.flow, self.build, obj, moves)], self.build)

    def transition_or_404(self, name):
        step = self.flow.get_transition(name or '')
        if step is None or step.auto or step.target not in self.build.states:
            raise Http404()
        return step

    def list(self, request, *args, **kwargs):
        return Response({'states': self.build.states})

    @action(detail=False, methods=['get'])
    def cards(self, request, *args, **kwargs):
        """The next page of one column: ``?state=<s>&offset=<n>``."""
        state = request.query_params.get('state')
        if state not in self.build.states:
            raise Http404()
        try:
            offset = max(int(request.query_params.get('offset', 0)), 0)
        except ValueError:
            offset = 0
        size = self.build.page_size
        objects = list(self.queryset().filter(flow_state=state).order_by(
            *card_ordering(self.build))[offset:offset + size + 1])
        moves = moves_for(self.flow, self.build, request.user)
        cards = [card(self.flow, self.build, obj, moves) for obj in objects[:size]]
        return Response({'state': state, 'count': len(cards),
                         'has_more': len(objects) > size,
                         'html': render_cards(cards, self.build)})

    @action(detail=True, methods=['get'])
    def transitions(self, request, pk=None, *args, **kwargs):
        """The transitions from the object's state to ``?target=<s>``: those
        the user may run now, and the others with why not."""
        obj = self.get_object(pk)
        target = request.query_params.get('target')
        if target not in self.build.states:
            raise Http404()
        flow, state = self.flow, obj.flow_state
        allowed, refused = [], []
        for step in flow.transitions:
            if step.auto or step.target != target or not flow.leaves(step, state):
                continue
            ok, reason = flow.check(step, obj, request.user)
            entry = {'name': step.name, 'label': str(step.label)}
            if ok:
                allowed.append({**entry, 'form': step.form is not None,
                                'css_class': step.css_class})
            else:
                refused.append({**entry, 'reason': str(reason)})
        detail = ''
        if not allowed:
            reasons = [item['reason'] for item in refused if item['reason']]
            detail = ' '.join(dict.fromkeys(reasons)) if reasons else _(
                'No transition goes from %(source)s to %(target)s.') % {
                'source': flow.state_label(state),
                'target': flow.state_label(target)}
        return Response({'state': state, 'target': target, 'transitions': allowed,
                         'refused': refused, 'detail': detail})

    def forms_for(self, step, obj, data=None, files=None):
        form = None
        if step.form is not None:
            kwargs = {'prefix': FORM_PREFIX}
            if issubclass(step.form, forms.ModelForm):
                kwargs['instance'] = obj
            form = step.form(data, files, **kwargs)
        return form, CommentForm(data, prefix=FORM_PREFIX + '_comment')

    def form_html(self, step, obj, form, comment):
        return render_to_string('gtdesigns/components/flow_kanban_form.html', {
            'transition': step, 'object': obj, 'form': form, 'comment_form': comment,
            'source': self.flow.state_label(obj.flow_state),
            'target': self.flow.state_label(step.target)}, request=self.request)

    def refused(self, reason):
        return Response({'detail': str(reason) or _('The card could not be moved.')},
                        status=403)

    @action(detail=True, methods=['get'])
    def form(self, request, pk=None, *args, **kwargs):
        """The modal of ``?transition=<t>``: its form and a comment."""
        obj = self.get_object(pk)
        step = self.transition_or_404(request.query_params.get('transition'))
        ok, reason = self.flow.check(step, obj, request.user)
        if not ok:
            return self.refused(reason)
        form, comment = self.forms_for(step, obj)
        return Response({'title': '%s: %s' % (step.label, obj),
                         'html': self.form_html(step, obj, form, comment)})

    @action(detail=True, methods=['post'])
    def move(self, request, pk=None, *args, **kwargs):
        """Run ``transition`` on the object, through ``Flow.run``."""
        # Optional app (see kanban_flow).
        from djgentelella.flows.exceptions import (  # noqa: PLC0415
            TransitionNotAllowed,
        )
        from djgentelella.flows.models import FlowInstance  # noqa: PLC0415
        obj = self.get_object(pk)
        step = self.transition_or_404(request.data.get('transition'))
        ok, reason = self.flow.check(step, obj, request.user)
        if not ok:
            return self.refused(reason)
        form, comment = self.forms_for(step, obj, request.data, request.FILES)
        valid = comment.is_valid()
        if form is not None:
            valid = form.is_valid() and valid
        if not valid:
            errors = {}
            for bound in (comment, form):
                if bound is not None:
                    errors.update({name: [item['message'] for item in items]
                                   for name, items in bound.errors.get_json_data()
                                   .items()})
            return Response({'errors': errors,
                             'html': self.form_html(step, obj, form, comment)},
                            status=400)
        try:
            instance = self.flow.run(obj, step.name, request.user, form=form,
                                     comment=comment.cleaned_data['comment'],
                                     request=request._request)
        except TransitionNotAllowed as error:
            # Someone moved it first, its condition changed, or an action
            # refused: nothing of the run was saved.
            return self.refused(error)
        moved = self.queryset().filter(pk=obj.pk).first()
        return Response({
            'pk': str(obj.pk), 'state': instance.state,
            'state_label': str(self.flow.state_label(instance.state)),
            'status': instance.status,
            'error': instance.error if instance.status == FlowInstance.ERROR else '',
            'card': self.card_html(moved) if moved is not None else None,
        })


FLOW_KANBAN_COMPONENTS = [FlowKanbanComponent]
