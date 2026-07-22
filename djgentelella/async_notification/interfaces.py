"""
Newsletter recipient interfaces.

A :class:`NewsLetterInterface` ties a base model + a filter form to a
queryset of recipient email addresses. Projects register their interfaces
via ``ASYNC_NEWS_BASE_MODELS`` (see settings) and reference them from
``NewsLetterTemplate.model_base``.
"""

from django.http import QueryDict
from django.utils.module_loading import import_string


class NewsLetterInterface:
    """Resolve newsletter recipients from a filtered model queryset.

    Subclasses declare:
        form: a Django ``Form`` class exposing filter/exclude fields.
        model: the Django model to query.
        email_field: field (or lookup path) holding the email address.
        field_map: ``{'filter': {form_field: orm_lookup},
                      'exclude': {form_field: orm_lookup}}``.
    """
    name = ''
    form = None
    model = None
    email_field = 'email'
    field_map = {'filter': {}, 'exclude': {}}

    def get_form(self, data=None):
        """Instantiate the filter form, bound to ``data`` when provided."""
        if self.form is None:
            return None
        return self.form(data) if data is not None else self.form()

    def get_filters(self, form):
        """Build ``.filter()`` kwargs from the bound form.

        Falsy values (unchecked checkboxes, blank fields) are treated as
        "no filter", matching the checkbox-as-toggle convention.
        """
        filters = {}
        form.is_valid()
        for field, lookup in self.field_map.get('filter', {}).items():
            value = form.cleaned_data.get(field)
            if value:
                filters[lookup] = value
        return filters

    def get_exclude(self, form):
        """Build ``.exclude()`` kwargs from the bound form.

        String values are split on commas into a list (e.g. an
        ``email__in`` exclusion).
        """
        excludes = {}
        for field, lookup in self.field_map.get('exclude', {}).items():
            value = form.cleaned_data.get(field)
            if value in (None, '', []):
                continue
            if isinstance(value, str):
                value = [v.strip() for v in value.split(',') if v.strip()]
            excludes[lookup] = value
        return excludes

    def get_queryset(self, form):
        """Return the model queryset with filters and exclusions applied."""
        queryset = self.model.objects.all()
        filters = self.get_filters(form)
        excludes = self.get_exclude(form)
        if filters:
            queryset = queryset.filter(**filters)
        if excludes:
            queryset = queryset.exclude(**excludes)
        return queryset

    def get_recipients(self, filters_querystring=''):
        """Resolve the filtered queryset into a list of email addresses.

        Args:
            filters_querystring: URL-encoded filter values from the stored
                ``NewsLetter.filters_querystring``.

        Returns:
            List of non-empty email addresses.
        """
        if self.model is None:
            return []
        if self.form is not None:
            form = self.get_form(QueryDict(filters_querystring or ''))
            queryset = self.get_queryset(form)
        else:
            queryset = self.model.objects.all()
        emails = queryset.values_list(self.email_field, flat=True)
        return [email for email in emails if email]


# ---------------------------------------------------------------------------
# Base-model registry (seeded from ASYNC_NEWS_BASE_MODELS in AppConfig.ready)
# ---------------------------------------------------------------------------

_NEWS_BASE_MODELS = {}


def register_news_basemodel(key, description, interface):
    """Register a newsletter base model.

    Args:
        key: The key stored in ``NewsLetterTemplate.model_base``.
        description: Human-readable label for the UI.
        interface: ``NewsLetterInterface`` subclass or dotted path to one.
    """
    if isinstance(interface, str):
        interface = import_string(interface)
    _NEWS_BASE_MODELS[key] = (key, description, interface)


def get_basemodel_info(key):
    """Return the ``(key, description, interface_class)`` tuple, or None."""
    return _NEWS_BASE_MODELS.get(key)


def get_basemodels_dict():
    """Return ``[(key, description), ...]`` for form choices."""
    return [(key, info[1]) for key, info in _NEWS_BASE_MODELS.items()]


def clear_basemodels():
    """Clear the registry. Useful for testing."""
    _NEWS_BASE_MODELS.clear()
