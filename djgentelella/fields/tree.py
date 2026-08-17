"""
Form fields for tree structured models, built on django-tree-queries.

``django-tree-queries`` only annotates ``tree_depth`` on querysets that went
through ``with_tree_fields()``, so these fields request it themselves and
callers can pass a plain queryset.

The labels are dicts rather than strings because
``gentelella/widgets/tree_select_option.html`` reads ``label.level``,
``label.disable`` and ``label.text`` to indent and disable the options.
"""
import re

from django import forms

from djgentelella.widgets import trees

DISABLE_KWARG = re.compile(r'^disable(\d+)$')


def pop_disabled_levels(kwargs):
    """Read ``disable0``, ``disable1``, ... out of ``kwargs``.

    A level is disabled only when its value is truthy, so ``disable1=False``
    leaves level 1 selectable.
    """
    levels = set()
    # The matches are materialised first: the loop pops from kwargs, and
    # iterating a dict while mutating it raises.
    matches = [(key, match) for key in kwargs
               if (match := DISABLE_KWARG.match(key))]
    for key, match in matches:
        if kwargs.pop(key):
            levels.add(int(match.group(1)))
    return levels


def with_tree_fields(queryset):
    """Ask django-tree-queries for ``tree_depth``, when the queryset supports it."""
    if queryset is not None and hasattr(queryset, 'with_tree_fields'):
        return queryset.with_tree_fields()
    return queryset


class TreeNodeChoiceMixin:
    """Turns each option label into the dict the tree option template expects."""

    def __init__(self, queryset, *args, **kwargs):
        self.disables = pop_disabled_levels(kwargs)
        super().__init__(queryset, *args, **kwargs)
        if getattr(self, 'empty_label', None) is not None:
            self.empty_label = {'level': 0, 'disable': False,
                                'text': self.empty_label}

    def _get_queryset(self):
        return self._queryset

    def _set_queryset(self, queryset):
        """Ask for ``tree_depth`` on every assignment, not only in ``__init__``.

        Narrowing the queryset afterwards is the normal way to scope a field::

            def __init__(self, user, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields['node'].queryset = MenuItem.objects.filter(...)

        That goes through this setter. Without it the new queryset carries no
        ``tree_depth``, ``label_from_instance`` falls back to level 0 and the
        whole tree renders flat with nothing disabled -- and no error to show
        for it.
        """
        super()._set_queryset(with_tree_fields(queryset))

    queryset = property(_get_queryset, _set_queryset)

    def label_from_instance(self, obj):
        level = getattr(obj, 'tree_depth', 0)
        return {'level': level, 'disable': level in self.disables,
                'text': str(obj)}


class GentelellaTreeNodeChoiceField(TreeNodeChoiceMixin, forms.ModelChoiceField):
    """Select one node, each option indented by its depth in the tree."""
    widget = trees.TreeSelect


class GentelellaTreeNodeMultipleChoiceField(TreeNodeChoiceMixin,
                                            forms.ModelMultipleChoiceField):
    """Select several nodes, each option indented by its depth in the tree."""
    widget = trees.TreeSelectMultiple
