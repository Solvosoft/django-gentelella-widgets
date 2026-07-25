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
    for key in [key for key in kwargs if DISABLE_KWARG.match(key)]:
        level = int(DISABLE_KWARG.match(key).group(1))
        if kwargs.pop(key):
            levels.add(level)
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
        super().__init__(with_tree_fields(queryset), *args, **kwargs)
        if getattr(self, 'empty_label', None) is not None:
            self.empty_label = {'level': 0, 'disable': False,
                                'text': self.empty_label}

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
