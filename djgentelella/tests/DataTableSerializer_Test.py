"""The DataTables envelope shared by every server-side table."""

from django.test import SimpleTestCase
from rest_framework import serializers

from djgentelella.history.serializers import HistoryDataTableSerializer
from djgentelella.serializers import DataTableSerializer


class Row(serializers.Serializer):
    name = serializers.CharField()


class RowDataTableSerializer(DataTableSerializer):
    data = serializers.ListField(child=Row(), required=True)


class DataTableSerializerTest(SimpleTestCase):
    envelope = {'draw': 3, 'recordsTotal': 10, 'recordsFiltered': 1}

    def test_a_subclass_serializes_its_rows_inside_the_envelope(self):
        payload = RowDataTableSerializer(
            {**self.envelope, 'data': [{'name': 'a', 'extra': 1}]}).data

        self.assertEqual(payload, {**self.envelope, 'data': [{'name': 'a'}]})

    def test_without_a_row_serializer_rows_pass_as_they_are(self):
        payload = DataTableSerializer(
            {**self.envelope, 'data': [{'name': 'a', 'extra': 1}]}).data

        self.assertEqual(payload['data'], [{'name': 'a', 'extra': 1}])

    def test_the_library_tables_share_it(self):
        self.assertTrue(issubclass(HistoryDataTableSerializer, DataTableSerializer))
