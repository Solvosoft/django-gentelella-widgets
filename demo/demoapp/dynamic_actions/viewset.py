from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated

from demoapp.models import DynamicContact
from djgentelella.lov import get_lov
from djgentelella.objectmanagement import BaseObjectManagement

LOV_FIELDS = {'country': 'demo_countries', 'province': 'demo_provinces',
              'canton': 'demo_cantons'}
PARENTS = {'province': ('country', 'country'), 'canton': ('province', 'province')}


class DynamicContactSerializer(serializers.ModelSerializer):
    actions = serializers.SerializerMethodField()

    def get_actions(self, obj):
        return {}

    class Meta:
        model = DynamicContact
        fields = '__all__'


class DynamicContactTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=DynamicContactSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class DynamicContactCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DynamicContact
        fields = '__all__'


class DynamicContactUpdateSerializer(serializers.ModelSerializer):
    """The LOV fields as ``{id, text}``: the update modal only has an
    ``<option>`` for what it is given, and that is how fill_form adds one."""

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for field, lov in LOV_FIELDS.items():
            value = data.get(field)
            if not value:
                data[field] = None
                continue
            parents = {}
            if field in PARENTS:
                param, source = PARENTS[field]
                parents[param] = getattr(instance, source)
            label = get_lov(lov).label(value, parents)
            data[field] = {'id': value, 'text': label or value}
        return data

    class Meta:
        model = DynamicContact
        fields = '__all__'


class DynamicContactManagement(BaseObjectManagement):
    serializer_class = {
        'list': DynamicContactTableSerializer,
        'create': DynamicContactCreateSerializer,
        'update': DynamicContactCreateSerializer,
        'retrieve': DynamicContactUpdateSerializer,
        'get_values_for_update': DynamicContactUpdateSerializer,
    }
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    queryset = DynamicContact.objects.all()
    search_fields = ['name', 'company_name']
    ordering_fields = ['name', 'total']
    ordering = ('-pk',)
