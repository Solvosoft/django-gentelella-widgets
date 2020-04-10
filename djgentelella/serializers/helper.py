from djgentelella.models import Help
from rest_framework import serializers

class HelperSerializer(serializers.ModelSerializer):
    class Meta:
        model = Help
        fields = ['id', 'id_view', 'question_name', 'help_title', 'help_text']
