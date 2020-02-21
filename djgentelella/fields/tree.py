from django.utils.encoding import smart_str
from django.utils.html import conditional_escape
from mptt.forms import TreeNodeChoiceField, TreeNodeMultipleChoiceField


class GentelellaTreeNodeChoiceField(TreeNodeChoiceField):

    def __init__(self, queryset, *args, **kwargs):
        self.disables = []
        for x in range(4):
            if 'disable'+str(x) in kwargs:
                self.disables.append(x)
                kwargs.pop('disable'+str(x))

        super().__init__(queryset, *args, **kwargs)

    def label_from_instance(self, obj):
        """
        Creates labels which represent the tree level of each node when
        generating option labels.
        """
        return conditional_escape(smart_str(obj))


    def label_from_instance(self, obj):
        """
        Convert objects into strings and generate the labels for the choices
        presented by this object. Subclasses can override this method to
        customize the display of the choices.
        """
        level = getattr(obj, obj._mptt_meta.level_attr)
        disable = False
        if level in self.disables:
            disable = True
        return {'level':level, 'disable': disable,  'text': str(obj) }


class GentelellaTreeNodeMultipleChoiceField(TreeNodeMultipleChoiceField):
    def __init__(self, queryset, *args, **kwargs):
        self.disables = []
        for x in range(4):
            if 'disable'+str(x) in kwargs:
                self.disables.append(x)
                kwargs.pop('disable'+str(x))

        super().__init__(queryset, *args, **kwargs)

    def label_from_instance(self, obj):
        """
        Creates labels which represent the tree level of each node when
        generating option labels.
        """
        return conditional_escape(smart_str(obj))

    def label_from_instance(self, obj):
        """
        Convert objects into strings and generate the labels for the choices
        presented by this object. Subclasses can override this method to
        customize the display of the choices.
        """
        level = getattr(obj, obj._mptt_meta.level_attr)
        disable = False
        if level in self.disables:
            disable = True
        return {'level':level, 'disable': disable,  'text': str(obj) }