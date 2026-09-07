from django.utils import formats
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from demoapp.models import Person, Country
from djgentelella.serializers import GTDateField, GTDateTimeField


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = '__all__'


class PersonSerializer(serializers.ModelSerializer):
    country = CountrySerializer()
    actions = serializers.SerializerMethodField()

    def get_actions(self, obj):
        return {
            'do': True
        }

    class Meta:
        model = Person
        fields = '__all__'


class PersonCardSerializer(serializers.ModelSerializer):
    country = CountrySerializer()
    actions = serializers.SerializerMethodField()

    def get_actions(self, obj):
        return [
            {
                'id': obj.pk,
                'name': 'edit',
                'icon': 'fa fa-edit',
                'title': _('Edit'),
            },
            {
                'id': obj.pk,
                'name': 'delete',
                'icon': 'fa fa-trash',
                'title': _('Delete'),
            },
        ]

    class Meta:
        model = Person
        fields = '__all__'


class PersonCardListSerializer(serializers.Serializer):
    data = PersonSerializer(many=True)  # Enviar datos estructurados
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class PersonCreateSerializer(serializers.ModelSerializer):
    born_date = GTDateField()
    # also can overwrite input_formats and format
    last_time = GTDateTimeField(
        allow_empty_str=True,
        # True it is  default value  allow "" as none and prevent validation error
        input_formats=[formats.get_format('DATETIME_INPUT_FORMATS')[0]],
        format=formats.get_format('DATETIME_INPUT_FORMATS')[0])

    def validate_num_children(self, value):
        num_children = value
        if num_children < 0:
            raise ValidationError(detail=_('Value has to be positive or zero '))
        return num_children

    class Meta:
        model = Person
        fields = '__all__'


class PersonUpdateSerializer(serializers.ModelSerializer):
    """Write side of the edit modal: PUT/PATCH.

    ``country`` is left to the default DRF behaviour -- a plain writable
    ``PrimaryKeyRelatedField`` -- on purpose. A nested ``CountrySerializer()``
    here would make it read-only for writes (DRF does not resolve nested
    objects back into a related instance without a custom ``update()``), and
    the whole point of this serializer is accepting the id the edit form
    submits.
    """
    born_date = GTDateField()
    last_time = GTDateTimeField()

    class Meta:
        model = Person
        fields = '__all__'


class PersonCardUpdateValuesSerializer(serializers.ModelSerializer):
    """Read side of the edit modal: what pre-fills the form when it opens.

    Unlike ``PersonUpdateSerializer``, ``country`` is nested here -- the edit
    form's select2 box needs the country's name to display, not just its id.
    Never used to accept a write, so the nested field being read-only is fine.
    """
    born_date = GTDateField()
    last_time = GTDateTimeField()
    country = CountrySerializer()

    class Meta:
        model = Person
        fields = ['id', 'name', 'num_children', 'country', 'born_date', 'last_time']
