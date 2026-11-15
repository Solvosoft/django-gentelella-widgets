"""A flow drawn as SVG on the server: no JavaScript, no dependency.

States are laid out in columns by their distance from ``initial`` (breadth
first), and within a column ordered after the states that lead to them, to
cross fewer edges. A forward transition is a curve from the right of its
source to the left of its target; one between two states of a column is a
straight line; one that goes back curves under the boxes. The transitions of
a ``'*'`` source come from a single "any state" node instead of from every
state. Activities other than states are drawn by their type (a switch as a
diamond-cornered box, a wait or a task with a mark) and the routes they
take are dashed, like automatic transitions.

With the runtime of an instance (:meth:`Flow.runtime`), the activities under
way, already done and failed are coloured: that is the instance's diagram.
The JSON it is drawn from is :meth:`Flow.as_graph`, which a client-side
library can use as well.
"""

from collections import deque

from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

WIDTH, HEIGHT = 150, 40
COLUMN, ROW = 270, 90
MARGIN = 30
LINE = 14
#: The id of the node that stands for ``'*'``.
ANY = '*'

STYLE = """
.gt-flow-node rect{fill:var(--bs-body-bg,#fff);stroke:var(--bs-secondary,#6c757d);
stroke-width:1.5}
.gt-flow-node.initial rect{stroke-width:3}
.gt-flow-node.final rect{stroke-dasharray:4 2}
.gt-flow-node.any rect{stroke-dasharray:2 3;fill:none}
.gt-flow-node.current rect,.gt-flow-node.active rect{fill:var(--bs-info,#0dcaf0);
stroke:var(--bs-info,#0dcaf0)}
.gt-flow-node.completed rect{fill:var(--bs-success-bg-subtle,#d1e7dd);
stroke:var(--bs-success,#198754)}
.gt-flow-node.error rect{fill:var(--bs-danger-bg-subtle,#f8d7da);
stroke:var(--bs-danger,#dc3545);stroke-width:3}
.gt-flow-node.switch rect,.gt-flow-node.parallel rect,.gt-flow-node.join rect{
stroke-dasharray:8 3}
.gt-flow-node .gt-flow-type{font:10px sans-serif;fill:var(--bs-secondary,#6c757d)}
.gt-flow-node text,.gt-flow-edge text{font:12px sans-serif;
fill:var(--bs-body-color,#212529)}
.gt-flow-edge text{paint-order:stroke;stroke:var(--bs-body-bg,#fff);stroke-width:4px;
stroke-linejoin:round}
.gt-flow-edge path{fill:none;stroke:var(--bs-secondary,#6c757d);stroke-width:1.2}
.gt-flow-edge.auto path{stroke-dasharray:5 3}
.gt-flow-edge.timeout path{stroke:var(--bs-danger,#dc3545)}
"""


def collapse_any(graph):
    """The graph with the edges a ``'*'`` source expands to replaced by one
    edge per transition, from an "any state" node."""
    edges, seen = [], set()
    for edge in graph['edges']:
        if not edge.get('any'):
            edges.append(edge)
        elif edge['name'] not in seen:
            seen.add(edge['name'])
            edges.append({**edge, 'source': ANY})
    nodes = list(graph['nodes'])
    if seen:
        nodes.append({'id': ANY, 'label': _('Any state'), 'initial': False,
                      'final': False, 'any': True})
    return {'nodes': nodes, 'edges': edges}


def layers(graph):
    """``{state: column}``: the breadth-first distance from the initial
    state; states it never reaches go in a column after the rest, and the
    "any state" node just before the first of its targets."""
    ids = [node['id'] for node in graph['nodes'] if node['id'] != ANY]
    initial = next((node['id'] for node in graph['nodes'] if node['initial']), ids[0])
    column = {initial: 0}
    queue = deque([initial])
    while queue:
        state = queue.popleft()
        for edge in graph['edges']:
            if edge['source'] == state and edge['target'] not in column:
                column[edge['target']] = column[state] + 1
                queue.append(edge['target'])
    last = max(column.values()) + 1
    found = {state: column.get(state, last) for state in ids}
    targets = [found[edge['target']] for edge in graph['edges']
               if edge['source'] == ANY]
    if targets:
        found[ANY] = max(min(targets) - 1, 0)
    return found


def rows(graph, column):
    """``{state: row}``: in each column, states ordered by the mean row of
    the states before them that lead there (the barycenter heuristic); the
    "any state" node goes last."""
    row = {}
    for index in range(max(column.values()) + 1):
        states = [node['id'] for node in graph['nodes']
                  if column[node['id']] == index]

        def weight(state, position):
            before = [row[edge['source']] for edge in graph['edges']
                      if edge['target'] == state and edge['source'] in row]
            if state == ANY:
                return (1, 0)
            return (0, sum(before) / len(before) if before else position)
        ordered = sorted(states, key=lambda state: weight(state, states.index(state)))
        row.update({state: position for position, state in enumerate(ordered)})
    return row


def _edges(graph):
    """Edges merged by (source, target), with all their labels."""
    merged = {}
    for edge in graph['edges']:
        key = (edge['source'], edge['target'])
        if key in merged:
            merged[key]['labels'].append(edge['label'])
            merged[key]['auto'] &= edge['auto']
            merged[key]['timeout'] |= edge['timeout']
        else:
            merged[key] = {**edge, 'labels': [edge['label']]}
    return merged.values()


def _curve(*points):
    return 'M%d,%d C%d,%d %d,%d %d,%d' % points


#: The mark drawn on the corner of each kind of activity.
TYPE_MARKS = {'switch': '\u25c7', 'wait': '\u23f1', 'parallel': '\u2016',
              'join': '\u2016', 'subflow': '\u21aa', 'human_task': '\u263a',
              'action': '\u2699'}


def render_svg(graph, current=None, runtime=None):
    """The SVG of ``graph``. ``current`` highlights one state; ``runtime``
    (``{'active': [...], 'completed': [...], 'error': [...]}``) the
    activities of an instance."""
    graph = collapse_any(graph)
    marks = {}
    for flag in ('completed', 'active', 'error'):  # the later wins
        for state in (runtime or {}).get(flag, ()):
            marks[state] = flag
    column = layers(graph)
    row = rows(graph, column)
    position = {state: (MARGIN + column[state] * COLUMN, MARGIN + row[state] * ROW)
                for state in column}
    width = MARGIN * 2 + max(column.values()) * COLUMN + WIDTH
    height = MARGIN * 2 + max(row.values()) * ROW + HEIGHT + ROW // 2
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" class="gt-flow-diagram" '
             'viewBox="0 0 %d %d" width="%d" style="max-width:100%%;height:auto" '
             'role="img">' % (width, height, width),
             '<defs><marker id="gt-flow-arrow" viewBox="0 0 10 10" refX="10" '
             'refY="5" markerWidth="7" markerHeight="7" orient="auto">'
             '<path d="M0,0L10,5L0,10z" fill="#6c757d"/></marker></defs>',
             '<style>%s</style>' % STYLE]
    labels = []
    for edge in _edges(graph):
        sx, sy = position[edge['source']]
        tx, ty = position[edge['target']]
        flags = [name for name in ('auto', 'timeout') if edge[name]]
        classes = ' '.join(['gt-flow-edge'] + flags)
        lines = [escape(text) for text in edge['labels']]
        anchor = 'middle'
        if edge['source'] == edge['target']:
            path = _curve(sx + WIDTH * 0.6, sy, sx + WIDTH * 0.6, sy - 35,
                          sx + WIDTH * 0.9, sy - 35, sx + WIDTH * 0.9, sy)
            lx, ly = sx + WIDTH * 0.75, sy - 30
        elif column[edge['target']] > column[edge['source']]:
            x1, y1 = sx + WIDTH, sy + HEIGHT / 2
            x2, y2 = tx, ty + HEIGHT / 2
            middle = (x1 + x2) / 2
            path = _curve(x1, y1, middle, y1, middle, y2, x2, y2)
            lx, ly = middle, (y1 + y2) / 2 - 6
        elif column[edge['target']] == column[edge['source']]:
            x = sx + WIDTH / 2
            y1, y2 = (sy + HEIGHT, ty) if ty > sy else (sy, ty + HEIGHT)
            path = 'M%d,%d L%d,%d' % (x, y1, x, y2)
            lx, ly, anchor = x + 6, (y1 + y2) / 2 + 4, 'start'
        else:  # back: under the boxes
            x1, y1 = sx + WIDTH / 2, sy + HEIGHT
            x2, y2 = tx + WIDTH / 2, ty + HEIGHT
            low = max(y1, y2) + ROW / 2
            path = _curve(x1, y1, x1, low, x2, low, x2, y2)
            lx, ly = (x1 + x2) / 2, low - 4
        parts.append('<g class="%s"><path d="%s" marker-end="url(#gt-flow-arrow)"/>'
                     '</g>' % (classes, path))
        # Labels after every path, so no line crosses over a text; one line
        # per transition, the block ending where a single label would sit.
        ly -= LINE * (len(lines) - 1)
        spans = ''.join(
            '<tspan x="%d" dy="%d">%s</tspan>' % (lx, LINE if index else 0, text)
            for index, text in enumerate(lines))
        labels.append('<g class="%s"><text x="%d" y="%d" text-anchor="%s">%s</text>'
                      '</g>' % (classes, lx, ly, anchor, spans))
    parts += labels
    for node in graph['nodes']:
        x, y = position[node['id']]
        flags = [name for name in ('initial', 'final', 'any') if node.get(name)]
        kind = node.get('type', 'state')
        if kind != 'state':
            flags.append(kind)
        if node['id'] == current:
            flags.append('current')
        if node['id'] in marks:
            flags.append(marks[node['id']])
        classes = ' '.join(['gt-flow-node'] + flags)
        mark = TYPE_MARKS.get(kind)
        mark = ('<text class="gt-flow-type" x="%d" y="%d">%s</text>' % (
            x + 6, y + 12, mark) if mark else '')
        parts.append('<g class="%s" data-state="%s" data-type="%s"%s><rect x="%d" '
                     'y="%d" width="%d" height="%d" rx="%d"/>%s<text x="%d" y="%d" '
                     'text-anchor="middle">%s</text></g>' % (
                         classes, escape(node['id']), escape(kind),
                         ' data-status="%s"' % marks[node['id']]
                         if node['id'] in marks else '',
                         x, y, WIDTH, HEIGHT, 2 if kind == 'switch' else 8, mark,
                         x + WIDTH / 2, y + HEIGHT / 2 + 4, escape(node['label'])))
    parts.append('</svg>')
    return mark_safe(''.join(parts))
