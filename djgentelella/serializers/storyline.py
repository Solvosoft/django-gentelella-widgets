from rest_framework import serializers


class DataSerializer(serializers.Serializer):
    data_column_name = serializers.CharField(required=True)
    datetime_format = serializers.CharField(required=True)  # still missing to validate date format
    datetime_column_name = serializers.CharField(required=True)
    url = serializers.CharField(required=True)


class ChartSerializer(serializers.Serializer):
    datetime_format = serializers.CharField(required=True)
    y_axis_label = serializers.CharField(required=False)


class CardSerializer(serializers.Serializer):
    title = serializers.CharField(required=True)
    text = serializers.CharField(required=True)
    row_number = serializers.CharField(required=True)
    display_date = serializers.CharField()


class SliderSerializer(serializers.Serializer):
    start_at_card = serializers.CharField()
    title_column_name = serializers.CharField(required=True)
    text_column_name = serializers.CharField(required=True)
    cards = CardSerializer(many=True, required=False)  # needs to check if cards work


class OptionsSerializer(serializers.Serializer):
    data = DataSerializer(required=True)
    chart = ChartSerializer(required=True)
    slider = SliderSerializer(required=True)
