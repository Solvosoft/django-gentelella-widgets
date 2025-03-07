from django.core.files.base import ContentFile
from django.test import TestCase
from rest_framework import serializers

from djgentelella.fields.files import GTBase64FileField


class GTBase64FileFieldTestCase(TestCase):
    def test_to_internal_value_with_valid_data(self):
        field = GTBase64FileField()
        data = {
            "name": "test.txt",
            "value": 'VGVzdCBjb250ZW50',
        }
        expected_content = ContentFile(b"Test content", name="test.txt")

        result = field.to_internal_value([data])

        self.assertEqual(result.read(), expected_content.read())
        self.assertEqual(result.name, expected_content.name)

    def test_to_internal_value_with_missing_fields(self):
        field = GTBase64FileField()
        data = {"name": "test.txt"}

        with self.assertRaises(serializers.ValidationError):
            field.to_internal_value(data)

    def test_to_internal_value_with_invalid_base64(self):
        field = GTBase64FileField()
        data = {
            "name": "test.txt",
            "value": "invalid_base64",
        }

        with self.assertRaises(serializers.ValidationError):
            field.to_internal_value(data)
