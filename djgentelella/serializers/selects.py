from rest_framework import serializers


class GTS2SerializerBase(serializers.Serializer):
    id_field = 'pk'
    display_fields = '__str__'
    default_selected = True
    default_disable = False

    def get_id(self, obj):
        return getattr(obj, self.id_field)

    def get_text(self, obj):
        if isinstance(self.display_fields, str):
            if self.display_fields == '__str__':
                return str(obj)
            return getattr(obj, self.display_fields)
        if isinstance(self.display_fields, (list, tuple)):
            lwords = [getattr(obj, key) for key in self.display_fields]
            return " ".join(lwords)
        return repr(obj)

    def get_selected(self, obj):
        return self.default_selected

    def get_disabled(self, obj):
        return self.default_disable

    id = serializers.SerializerMethodField()
    text = serializers.SerializerMethodField()
    disabled = serializers.SerializerMethodField()
    selected = serializers.SerializerMethodField()


class ChoicesGTS2Serializer(GTS2SerializerBase):
    def __init__(self, *args, choices=None, **kwargs):
        self.choices = dict(choices)
        super().__init__(*args, **kwargs)

    def get_id(self, obj):
        return obj

    def get_text(self, obj):
        if obj in self.choices:
            return self.choices[obj]
        return obj
