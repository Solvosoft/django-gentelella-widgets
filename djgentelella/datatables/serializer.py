from django.utils import formats
from django.utils.translation import gettext_lazy as _
from django_filters import DateFromToRangeFilter, DateTimeFromToRangeFilter
from django_filters import FilterSet
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


from djgentelella.blog.models import Entry, Category, EntryImage
from djgentelella.fields.drfdatetime import DateRangeTextWidget, DateTimeRangeTextWidget






class BlogFilterSet(FilterSet):


    class Meta:
        model = Entry
        fields = {'title': ['icontains'], 'resume': ['icontains'], 'content': ['icontains'], }


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


#ESTE ES PARA CATEGORIAS y author
class BlogSerializer(serializers.ModelSerializer):
    #categories = CategorySerializer()
    categories = serializers.StringRelatedField(many=True)
    author = serializers.StringRelatedField(many=False)
    published_content = serializers.StringRelatedField(required=False)  # Campo no requerido
    actions = serializers.SerializerMethodField()

    def get_actions(self, obj):
        return {
            'do': True
        }

    class Meta:
        model = Entry
        fields = "__all__"


#ESTE ES PARA AUTHOR
class BlogDataTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=BlogSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)
    published_content = serializers.StringRelatedField(required=False)



class BlogCreateSerializer(serializers.ModelSerializer):
    published_content = serializers.StringRelatedField(required=False)
    class Meta:
        model = Entry
        fields = "__all__"



class CategorySerializer(serializers.ModelSerializer):
    published_content = serializers.StringRelatedField(required=False)


    class Meta:
            model = Category
            fields = '__all__'


class BlogUpdateSerializer(serializers.ModelSerializer):
    published_content = serializers.StringRelatedField(required=False)
    #categories = serializers.StringRelatedField(many=True) #AGRGADO
   # categories = CategorySerializer(many=True)
    categories = serializers.StringRelatedField(
        many=True)  # Muestra el nombre de la categoría

    class Meta:
        model = Entry
        fields = "__all__"
