from django.utils import formats
from django_filters import DateFromToRangeFilter, DateTimeFromToRangeFilter, FilterSet
from rest_framework import serializers

from demoapp.models import ObjectManagerDemoModel
from djgentelella.fields.drfdatetime import DateRangeTextWidget, DateTimeRangeTextWidget
from djgentelella.fields.files import GTBase64FileField, ChunkedFileField
from djgentelella.serializers import GTDateField, GTDateTimeField
from djgentelella.serializers.selects import GTS2SerializerBase


class ASerializer(GTS2SerializerBase):
    display_fields = 'display'


# GTS2SerializerBase
class ObjectManagerDemoModelSerializer(serializers.ModelSerializer):
    born_date = GTDateField()
    # also can overwrite input_formats and format
    last_time = GTDateTimeField(
        allow_empty_str=True,
        # True it is  default value  allow "" as none and prevent validation error
        input_formats=[formats.get_format('DATETIME_INPUT_FORMATS')[0]],
        format=formats.get_format('DATETIME_INPUT_FORMATS')[0])

    field_autocomplete = GTS2SerializerBase()
    m2m_autocomplete = GTS2SerializerBase(many=True)
    field_select = GTS2SerializerBase()
    m2m_multipleselect = ASerializer(many=True)

    actions = serializers.SerializerMethodField()

    def get_actions(self, obj):
        if obj.id % 4 == 1:
            return {
                'destroy': False,
                'update': False,
                'detail': True
            }
        elif obj.id % 4 == 2:
            return {
                'destroy': False,
                'update': True,
                'detail': True
            }
        elif obj.id % 4 == 3:
            return {
                'detail': False
            }
        return {}

    class Meta:
        model = ObjectManagerDemoModel
        fields = '__all__'


class ObjectManagerDemoModelTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=ObjectManagerDemoModelSerializer(),
                                 required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class ObjectManagerDemoModelCreateSerializer(serializers.ModelSerializer):
    born_date = GTDateField()
    last_time = GTDateTimeField()
    simple_archive = GTBase64FileField(allow_empty_file=False)
    chunked_archive = ChunkedFileField()

    class Meta:
        model = ObjectManagerDemoModel
        fields = "__all__"


class ObjectManagerDemoModelUpdateSerializer(serializers.ModelSerializer):
    born_date = GTDateField()
    last_time = GTDateTimeField()
    simple_archive = GTBase64FileField()
    chunked_archive = ChunkedFileField()

    field_autocomplete = GTS2SerializerBase()
    m2m_autocomplete = GTS2SerializerBase(many=True)
    field_select = GTS2SerializerBase()
    m2m_multipleselect = ASerializer(many=True)

    class Meta:
        model = ObjectManagerDemoModel
        fields = "__all__"


class ObjectManagerDemoModelFilterSet(FilterSet):
    born_date = DateFromToRangeFilter(
        widget=DateRangeTextWidget(attrs={'placeholder': 'YYYY/MM/DD'}))
    last_time = DateTimeFromToRangeFilter(
        widget=DateTimeRangeTextWidget(attrs={'placeholder': 'YYYY/MM/DD HH:MM:SS'}))
    livetime_range = DateFromToRangeFilter(
        widget=DateRangeTextWidget(attrs={'placeholder': 'YYYY/MM/DD'}))

    class Meta:
        model = ObjectManagerDemoModel
        fields = {'name': ['icontains'],
                  'float_number': ['exact'],
                  'knob_number': ['exact'],
                  'radio_elements': ['exact'],
                  'description': ['icontains'],
                  'field_autocomplete': ['exact']
                  }
