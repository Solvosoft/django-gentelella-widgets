from djgentelella.objectmanagement import AuthAllPermBaseObjectManagement
from django.utils.translation import gettext_lazy as _
from djgentelella.history.utils import add_log
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from djgentelella.history.serializers import HistoryDataTableSerializer
from djgentelella.history.filterset import HistoryFilterSet
from rest_framework.authentication import SessionAuthentication
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import LimitOffsetPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from django.conf import settings
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType



class BaseViewSetWithLogs(AuthAllPermBaseObjectManagement):

    def perform_create(self, serializer):
        super().perform_create(serializer)
        new_instance = serializer.instance

        add_log(
            self.request.user,
            new_instance,
            ADDITION,
            new_instance._meta.verbose_name.title().lower(),
            [],
            change_message=_("Created"),
        )

    def perform_update(self, serializer):
        # get the instance before the update
        instance = self.get_object()
        old_values = {
            field: getattr(instance, field)
            for field in serializer.validated_data.keys()
        }

        super().perform_update(serializer)

        new_instance = serializer.instance
        # get changed fields
        changed_fields = []

        for field in serializer.validated_data.keys():
            old_value = old_values.get(field)
            new_value = getattr(new_instance, field)
            if old_value != new_value:
                changed_fields.append(field)

        add_log(
            self.request.user,
            new_instance,
            CHANGE,
            new_instance._meta.verbose_name.title().lower(),
            changed_data=changed_fields,
            change_message=_("Updated"),
        )

    def perform_destroy(self, instance):
        instance = self.get_object()
        if instance._meta.verbose_name.title() in self.models_log:
            add_log(
                self.request.user,
                instance,
                DELETION,
                instance._meta.verbose_name.title().lower(),
                change_message=_("Deleted"),
            )

        super().perform_destroy(instance)


class HistoryViewSet(AuthAllPermBaseObjectManagement):
    authentication_classes = [SessionAuthentication]
    serializer_class = HistoryDataTableSerializer
    queryset = LogEntry.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ["object_repr"]
    filterset_class = HistoryFilterSet
    ordering_fields = ["-action_time"]
    ordering = ("-action_time",)
    perms = {"list": ["admin.view_logentry"]}

    def get_queryset(self):
        queryset = self.queryset

        # check allowed models in settings
        allowed = getattr(settings, "GT_HISTORY_ALLOWED_MODELS", None)

        if allowed:
            allowed_ctypes = self.contenttypes_from_settings(allowed)

            if not allowed_ctypes.exists():
                return queryset.none()

            queryset = queryset.filter(content_type__in=allowed_ctypes).distinct()


        # check contenttype param in form
        ctypes_param = self.request.GET.get("contenttype")
        if ctypes_param and ctypes_param in allowed:

            ctypes_qs = self.contenttypes_from_settings([ctypes_param])

            if not ctypes_qs.exists():
                return queryset.none()

            queryset = queryset.filter(content_type__in=ctypes_qs).distinct()

        # default values
        return queryset

    def contenttypes_from_settings(self, entries):
        q = Q()
        for item in entries:
            if isinstance(item, str) and "." in item:
                app_label, model_name = item.split(".", 1)
                app_label = app_label.strip()
                model_key = model_name.strip().lower()
                q |= Q(app_label=app_label, model=model_key)

        if not q:
            return ContentType.objects.none()
        return ContentType.objects.filter(q)


    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        data = page if page is not None else queryset

        response = {
            "data": data,
            "recordsTotal": LogEntry.objects.count(),
            "recordsFiltered": queryset.count(),
            "draw": self.request.GET.get("draw", 1),
        }
        return Response(self.get_serializer(response).data)
