from django.db.models import JSONField
from django.forms import Field

from djgentelella.widgets.multiwidget import MultiWidgetWidget


class MultiWidgetJsonField(JSONField):
    def from_db_value(self, value, expression, connection):
        dev = super().from_db_value(value, expression, connection)
        return dev

    def formfield(self, **kwargs):
        field = super().formfield(**kwargs)
        old_widget = field.widget
        field.widget = MultiWidgetWidget()
        field.widget.is_localized = old_widget.is_localized
        field.widget.is_required = old_widget.is_required

        # Hook into self.widget_attrs() for any Field-specific HTML attributes.
        extra_attrs = Field.widget_attrs(self, field.widget)
        if extra_attrs:
            field.widget.attrs.update(extra_attrs)
        return field

    def get_db_prep_value(self, value, connection, prepared=False):
        return super().get_db_prep_value(value, connection, prepared=prepared)
