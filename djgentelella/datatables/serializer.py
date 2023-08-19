from django.utils import formats
from django.utils.translation import gettext_lazy as _
from django_filters import DateFromToRangeFilter, DateTimeFromToRangeFilter
from django_filters import FilterSet
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

#from demoapp.models import Person, Country
from djgentelella.blog.models import Entry, Category, EntryImage
from djgentelella.fields.drfdatetime import DateRangeTextWidget, DateTimeRangeTextWidget
from djgentelella.serializers import GTDateField, GTDateTimeField


class BlogFilterSet(FilterSet):

    class Meta:
        model = Entry
        fields = {'title': ['icontains'], 'resume': ['icontains']}


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


class BlogSerializer(serializers.ModelSerializer):
   # Category = CategorySerializer()
    actions = serializers.SerializerMethodField()

    def get_actions(self, obj):
        return {
            'do': True
        }

    class Meta:
        model = Entry
        fields = "__all__"


class BlogDataTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=BlogSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class BlogCreateSerializer(serializers.ModelSerializer):
    born_date = GTDateField()
    # also can overwrite input_formats and format
    last_time = GTDateTimeField(
        allow_empty_str=True,
        # True it is  default value  allow "" as none and prevent validation error
        input_formats=[formats.get_format('DATETIME_INPUT_FORMATS')[0]],
        format=formats.get_format('DATETIME_INPUT_FORMATS')[0])

#################################
   # def validate_num_children(self, value):
     #   num_children = value
     #   if num_children < 0:
      #      raise ValidationError(detail=_("Value has to be positive or zero "))
     #   return num_children
#########################

    class Meta:
        model = Entry
        fields = "__all__"


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class BlogUpdateSerializer(serializers.ModelSerializer):
    born_date = GTDateField()
    last_time = GTDateTimeField()
    country = CategorySerializer()

    class Meta:
        model = Entry
        fields = "__all__"
