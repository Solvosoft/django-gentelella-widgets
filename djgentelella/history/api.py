from django.conf import settings
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.authentication import SessionAuthentication
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from djgentelella.history.filterset import HistoryFilterSet
from djgentelella.history.serializers import HistoryDataTableSerializer
from djgentelella.history.utils import add_log
from djgentelella.models import DeletedWithTrash
from djgentelella.objectmanagement import AuthAllPermBaseObjectManagement
from djgentelella.utils import contenttypes_from_labels


class BaseViewSetWithLogs(AuthAllPermBaseObjectManagement):
    """CRUD viewset that writes an audit entry for create/update/destroy.

    ``models_log`` is an optional allowlist of ``app_label.model`` labels:
    ``None`` (the default) logs everything the viewset touches.  The hooks
    ``get_log_related_objects()`` / ``get_log_extra()`` let a subclass attach
    related instances and arbitrary JSON to every entry; with
    ``log_request_metadata`` on (the default), the requesting browser and
    address are recorded on their own.
    """

    models_log = None
    log_request_metadata = True

    def should_log(self, instance):
        allowed = getattr(self, 'models_log', None)
        if allowed is None:
            return True
        return instance._meta.label_lower in {
            str(item).lower() for item in allowed
        }

    def get_log_related_objects(self, instance):
        """Instances this action also touched (see add_log related_objects)."""
        return None

    def get_log_extra(self, instance):
        """Arbitrary JSON payload for the entry; merged with request metadata."""
        return None

    def _log_extra(self, instance):
        extra = self.get_log_extra(instance) or {}
        if self.log_request_metadata and getattr(self, 'request', None):
            meta = self.request.META
            extra.setdefault('user_agent', meta.get('HTTP_USER_AGENT', ''))
            extra.setdefault(
                'ip',
                (meta.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                 or meta.get('REMOTE_ADDR', '')),
            )
            extra.setdefault('method', self.request.method)
            extra.setdefault('path', self.request.path)
        return extra or None

    def _add_log(self, instance, action_flag, changed_data, change_message):
        add_log(
            self.request.user,
            instance,
            action_flag,
            instance._meta.verbose_name.title().lower(),
            changed_data,
            change_message=change_message,
            related_objects=self.get_log_related_objects(instance),
            extra=self._log_extra(instance),
        )

    def perform_create(self, serializer):
        super().perform_create(serializer)
        new_instance = serializer.instance
        if self.should_log(new_instance):
            self._add_log(new_instance, ADDITION, [], _('Created'))

    def perform_update(self, serializer):
        instance = self.get_object()

        # Snapshot through the serializer's own sources, so a field whose
        # name is not a model attribute (source=, write_only, nested) is
        # skipped instead of raising AttributeError.
        sources = {}
        for name, field in serializer.fields.items():
            if name not in serializer.validated_data:
                continue
            source = field.source or name
            if '.' in source or not hasattr(instance, source):
                continue
            sources[name] = source
        old_values = {
            name: getattr(instance, source) for name, source in sources.items()
        }

        super().perform_update(serializer)

        new_instance = serializer.instance
        changed_fields = []
        for name, source in sources.items():
            try:
                new_value = getattr(new_instance, source)
            except AttributeError:
                continue
            if old_values.get(name) != new_value:
                changed_fields.append(source)

        if self.should_log(new_instance):
            self._add_log(new_instance, CHANGE, changed_fields, _('Updated'))

    def perform_destroy(self, instance):
        instance = self.get_object()
        if self.should_log(instance):
            self._add_log(instance, DELETION, None, _('Deleted'))

        # Soft-deletable instances record who threw them away.
        if isinstance(instance, DeletedWithTrash):
            instance.delete(user=self.request.user)
        else:
            super().perform_destroy(instance)


class HistoryViewSet(AuthAllPermBaseObjectManagement):
    authentication_classes = [SessionAuthentication]
    serializer_class = HistoryDataTableSerializer
    queryset = LogEntry.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['object_repr']
    filterset_class = HistoryFilterSet
    ordering_fields = ['-action_time']
    ordering = ('-action_time',)
    perms = {'list': ['admin.view_logentry']}

    def get_queryset(self):
        queryset = self.queryset

        # check allowed models in settings
        allowed = getattr(settings, 'GT_HISTORY_ALLOWED_MODELS', None)

        if allowed:
            allowed_ctypes = self.contenttypes_from_settings(allowed)

            if not allowed_ctypes.exists():
                return queryset.none()

            queryset = queryset.filter(content_type__in=allowed_ctypes).distinct()

        # check contenttype param in form. Without the setting, every model
        # is allowed.
        ctypes_param = self.request.GET.get('contenttype')
        if ctypes_param and (not allowed or ctypes_param in allowed):

            ctypes_qs = self.contenttypes_from_settings([ctypes_param])

            if not ctypes_qs.exists():
                return queryset.none()

            queryset = queryset.filter(content_type__in=ctypes_qs).distinct()

        queryset = self.filter_by_related(queryset)

        return self.scope_queryset(queryset)

    def filter_by_related(self, queryset):
        """Entries whose HistoryRelation points at the given object.

        Driven by the generic query params ``related_contenttype``
        (``app.model``) and ``related_id`` (repeatable).
        """
        related_ct = self.request.GET.get('related_contenttype')
        if not related_ct:
            return queryset
        ctypes = self.contenttypes_from_settings([related_ct])
        if not ctypes.exists():
            return queryset.none()
        filters = {'gt_relations__content_type__in': ctypes}
        related_ids = self.request.GET.getlist('related_id')
        if related_ids:
            filters['gt_relations__object_id__in'] = related_ids
        return queryset.filter(**filters).distinct()

    def scope_queryset(self, queryset):
        """Last word on what this request may see.

        The default is everything the settings allow; a multi-tenant project
        overrides this to cut the log down to the requester's organization.
        """
        return queryset

    def contenttypes_from_settings(self, entries):
        return contenttypes_from_labels(entries)

    def list(self, request, *args, **kwargs):
        # recordsTotal counts the scoped universe, not the whole table: a
        # raw LogEntry.objects.count() would leak the global log volume into
        # every tenant's DataTable footer.
        base_queryset = self.get_queryset()
        queryset = self.filter_queryset(base_queryset)
        page = self.paginate_queryset(queryset)
        data = page if page is not None else queryset

        response = {
            'data': data,
            'recordsTotal': base_queryset.count(),
            'recordsFiltered': queryset.count(),
            'draw': self.request.GET.get('draw', 1),
        }
        return Response(self.get_serializer(response).data)
