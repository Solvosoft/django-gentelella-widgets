from rest_framework import serializers

from djgentelella.models import Help


class HelperSerializer(serializers.ModelSerializer):
    class Meta:
        model = Help
        fields = ['id', 'id_view', 'question_name', 'help_title', 'help_text']
