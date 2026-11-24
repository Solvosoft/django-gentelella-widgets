from django.apps import AppConfig


class SearchTrigramConfig(AppConfig):
    name = 'djgentelella.search.trigram'
    label = 'gtsearch_trigram'
    verbose_name = 'Global search: pg_trgm'
