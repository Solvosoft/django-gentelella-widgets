"""
Views for the async_notification module.

Contains both DRF ViewSets for the API and server-rendered HTML views.
"""

import json
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from djgentelella.objectmanagement import AuthAllPermBaseObjectManagement

from djgentelella.async_notification.backends import get_backend
from djgentelella.async_notification.forms import (
    EmailNotificationForm, EmailTemplateForm,
    NewsLetterTemplateForm, NewsLetterForm, NewsLetterTaskForm
)
from djgentelella.async_notification.introspection import get_fields_for_context, get_fields_for_content_types
from djgentelella.async_notification.models import (
    EmailNotification, EmailTemplate, AttachedFile,
    NewsLetterTemplate, NewsLetter, NewsLetterTask
)
from djgentelella.async_notification.resolvers import RecipientResolverRegistry
from djgentelella.async_notification.sending import (
    do_send_notification, do_send_newsletter_direct, resolve_all_recipients
)
from djgentelella.async_notification.serializers import (
    EmailNotificationSerializer, EmailNotificationTableSerializer,
    EmailNotificationCreateSerializer, EmailNotificationDetailSerializer,
    EmailNotificationFilterSet,
    EmailTemplateSerializer, EmailTemplateTableSerializer,
    EmailTemplateCreateSerializer, EmailTemplateDetailSerializer,
    NewsLetterTemplateSerializer, NewsLetterTemplateTableSerializer,
    NewsLetterTemplateCreateSerializer, NewsLetterTemplateDetailSerializer,
    NewsLetterSerializer, NewsLetterTableSerializer,
    NewsLetterCreateSerializer, NewsLetterDetailSerializer,
    NewsLetterTaskSerializer, NewsLetterTaskTableSerializer,
    NewsLetterTaskCreateSerializer, NewsLetterTaskDetailSerializer,
    NewsLetterTaskFilterSet,
)
from djgentelella.async_notification.settings import (
    ASYNC_NOTIFICATION_USER_LOOKUP_FIELDS,
)

logger = logging.getLogger(__name__)
User = get_user_model()

APP_PERM_PREFIX = 'async_notification'


# =============================================================================
# API ViewSets
# =============================================================================

class EmailNotificationManagement(AuthAllPermBaseObjectManagement):
    serializer_class = {
        'list': EmailNotificationTableSerializer,
        'create': EmailNotificationCreateSerializer,
        'update': EmailNotificationCreateSerializer,
        'retrieve': EmailNotificationDetailSerializer,
        'get_values_for_update': EmailNotificationDetailSerializer,
        'destroy': EmailNotificationSerializer,
        'send_email': EmailNotificationSerializer,
        'send_selected': EmailNotificationSerializer,
        'send_selected_via_task': EmailNotificationSerializer,
        'send_selected_via_django_task': EmailNotificationSerializer,
        'send_test_from_template': EmailNotificationSerializer,
    }
    perms = {
        'list': [f'{APP_PERM_PREFIX}.view_emailnotification'],
        'create': [f'{APP_PERM_PREFIX}.add_emailnotification'],
        'update': [f'{APP_PERM_PREFIX}.change_emailnotification'],
        'retrieve': [f'{APP_PERM_PREFIX}.view_emailnotification'],
        'get_values_for_update': [f'{APP_PERM_PREFIX}.change_emailnotification'],
        'destroy': [f'{APP_PERM_PREFIX}.delete_emailnotification'],
        'send_email': [f'{APP_PERM_PREFIX}.change_emailnotification'],
        'send_selected': [f'{APP_PERM_PREFIX}.change_emailnotification'],
        'send_selected_via_task': [f'{APP_PERM_PREFIX}.change_emailnotification'],
        'send_selected_via_django_task': [f'{APP_PERM_PREFIX}.change_emailnotification'],
        'send_test_from_template': [f'{APP_PERM_PREFIX}.add_emailnotification'],
    }
    queryset = EmailNotification.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['subject', 'recipients', 'status']
    filterset_class = EmailNotificationFilterSet
    ordering_fields = ['created_at', 'subject', 'status']
    ordering = ('-created_at',)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def send_email(self, request, pk=None):
        """Send a single email notification now."""
        notification = self.get_object()
        if notification.status == 'sent':
            return Response({'result': False,
                            'detail': 'Already sent'}, status=400)
        do_send_notification(notification.pk)
        notification.refresh_from_db()
        return Response({
            'result': notification.status == 'sent',
            'detail': f'Status: {notification.status}',
        })

    @action(detail=False, methods=['post'])
    def send_selected(self, request):
        """Send multiple selected notifications."""
        pks = request.data.get('pks', [])
        if not pks:
            return Response({'result': False,
                            'detail': 'No notifications selected'},
                           status=400)
        sent = 0
        for pk in pks:
            try:
                do_send_notification(pk)
                sent += 1
            except Exception as e:
                logger.error('Error sending notification %s: %s', pk, e)
        return Response({
            'result': True,
            'detail': f'{sent} notifications processed',
        })

    @action(detail=False, methods=['post'], url_path='send-via-task', url_name='send-via-task')
    def send_selected_via_task(self, request):
        """Enqueue multiple selected notifications via the configured backend (Celery)."""
        pks = request.data.get('pks', [])
        if not pks:
            return Response({'result': False,
                            'detail': 'No notifications selected'},
                           status=400)
        backend = get_backend()
        queued = 0
        for pk in pks:
            try:
                backend.send(pk)
                queued += 1
            except Exception as e:
                logger.error('Error queuing notification %s: %s', pk, e)
        return Response({
            'result': True,
            'detail': f'{queued} notifications enqueued via {backend.__class__.__name__}',
        })

    @action(detail=False, methods=['post'], url_path='send-via-django-task', url_name='send-via-django-task')
    def send_selected_via_django_task(self, request):
        """Enqueue multiple selected notifications via Django Tasks backend."""
        from djgentelella.async_notification.backends.django_tasks import DjangoTasksBackend
        pks = request.data.get('pks', [])
        if not pks:
            return Response({'result': False,
                            'detail': 'No notifications selected'},
                           status=400)
        backend = DjangoTasksBackend()
        queued = 0
        for pk in pks:
            try:
                backend.send(pk)
                queued += 1
            except Exception as e:
                logger.error('Error queuing notification %s: %s', pk, e)
        return Response({
            'result': True,
            'detail': f'{queued} notifications enqueued via DjangoTasksBackend',
        })

    @action(detail=False, methods=['post'], url_path='send-test-template', url_name='send-test-template')
    def send_test_from_template(self, request):
        """Send a test email using send_email_from_template and dispatch via backend."""
        from djgentelella.async_notification.sending import send_email_from_template

        code = request.data.get('code')
        recipient = request.data.get('recipient') or request.user.email

        if not code:
            template = EmailTemplate.objects.first()
            if not template:
                return Response({'result': False,
                                'detail': 'No templates found. Run create_notification_demo first.'},
                               status=400)
            code = template.code

        if not recipient:
            return Response({'result': False,
                            'detail': 'No recipient: provide one or set an email on your user account.'},
                           status=400)

        order = {
            'id': 'TEST-001',
            'total': '1000.00',
            'delivery_date': '2023-01-01',
        }

        context = {
            'user': request.user,
            'order': order,
        }

        try:
            notification = send_email_from_template(
                code=code,
                recipient=recipient,
                context=context,
                enqueued=False,
                user=request.user,
            )
            #get_backend().send(notification.pk)
        except EmailTemplate.DoesNotExist:
            return Response({'result': False,
                            'detail': f'Template "{code}" not found.'},
                           status=400)

        return Response({
            'result': True,
            'detail': f'Test email from template "{code}" dispatched to {recipient} '
                      f'via {get_backend().__class__.__name__} (notification #{notification.pk})',
        })


class EmailTemplateManagement(AuthAllPermBaseObjectManagement):
    serializer_class = {
        'list': EmailTemplateTableSerializer,
        'create': EmailTemplateCreateSerializer,
        'update': EmailTemplateCreateSerializer,
        'retrieve': EmailTemplateDetailSerializer,
        'get_values_for_update': EmailTemplateDetailSerializer,
        'destroy': EmailTemplateSerializer,
        'preview': EmailTemplateSerializer,
    }
    perms = {
        'list': [f'{APP_PERM_PREFIX}.view_emailtemplate'],
        'create': [f'{APP_PERM_PREFIX}.add_emailtemplate'],
        'update': [f'{APP_PERM_PREFIX}.change_emailtemplate'],
        'retrieve': [f'{APP_PERM_PREFIX}.view_emailtemplate'],
        'get_values_for_update': [f'{APP_PERM_PREFIX}.change_emailtemplate'],
        'destroy': [f'{APP_PERM_PREFIX}.delete_emailtemplate'],
        'preview': [f'{APP_PERM_PREFIX}.view_emailtemplate'],
    }
    queryset = EmailTemplate.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['code', 'subject']
    ordering_fields = ['created_at', 'code', 'subject']
    ordering = ('-created_at',)

    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        """Preview an email template."""
        from djgentelella.async_notification.introspection import get_fields_for_content_types
        from djgentelella.async_notification.preview import build_dummy_context_from_fields, render_preview

        template = self.get_object()
        ct_pks = list(template.context_models.values_list('pk', flat=True))
        fields_data = get_fields_for_content_types(ct_pks) or {}
        context = build_dummy_context_from_fields(fields_data) if fields_data else {}

        return Response({
            'subject': render_preview(template.subject, context),
            'message': render_preview(template.message, context, template.base_template or None),
            'context_models': ct_pks,
            'base_template': template.base_template,
        })


class NewsLetterTemplateManagement(AuthAllPermBaseObjectManagement):
    serializer_class = {
        'list': NewsLetterTemplateTableSerializer,
        'create': NewsLetterTemplateCreateSerializer,
        'update': NewsLetterTemplateCreateSerializer,
        'retrieve': NewsLetterTemplateDetailSerializer,
        'get_values_for_update': NewsLetterTemplateDetailSerializer,
        'destroy': NewsLetterTemplateSerializer,
    }
    perms = {
        'list': [f'{APP_PERM_PREFIX}.view_newslettertemplate'],
        'create': [f'{APP_PERM_PREFIX}.add_newslettertemplate'],
        'update': [f'{APP_PERM_PREFIX}.change_newslettertemplate'],
        'retrieve': [f'{APP_PERM_PREFIX}.view_newslettertemplate'],
        'get_values_for_update': [f'{APP_PERM_PREFIX}.change_newslettertemplate'],
        'destroy': [f'{APP_PERM_PREFIX}.delete_newslettertemplate'],
    }
    queryset = NewsLetterTemplate.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['title', 'slug']
    ordering_fields = ['created_at', 'title']
    ordering = ('-created_at',)


class NewsLetterManagement(AuthAllPermBaseObjectManagement):
    serializer_class = {
        'list': NewsLetterTableSerializer,
        'create': NewsLetterCreateSerializer,
        'update': NewsLetterCreateSerializer,
        'retrieve': NewsLetterDetailSerializer,
        'get_values_for_update': NewsLetterDetailSerializer,
        'destroy': NewsLetterSerializer,
        'preview': NewsLetterSerializer,
        'preview_recipients': NewsLetterSerializer,
        'send_selected': NewsLetterSerializer,
    }
    perms = {
        'list': [f'{APP_PERM_PREFIX}.view_newsletter'],
        'create': [f'{APP_PERM_PREFIX}.add_newsletter'],
        'update': [f'{APP_PERM_PREFIX}.change_newsletter'],
        'retrieve': [f'{APP_PERM_PREFIX}.view_newsletter'],
        'get_values_for_update': [f'{APP_PERM_PREFIX}.change_newsletter'],
        'destroy': [f'{APP_PERM_PREFIX}.delete_newsletter'],
        'preview': [f'{APP_PERM_PREFIX}.view_newsletter'],
        'preview_recipients': [f'{APP_PERM_PREFIX}.view_newsletter'],
        'send_selected': [f'{APP_PERM_PREFIX}.change_newsletter'],
    }
    queryset = NewsLetter.objects.select_related('template', 'created_by')
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['subject']
    ordering_fields = ['created_at', 'subject']
    ordering = ('-created_at',)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['post'], url_path='send-selected', url_name='send-selected')
    def send_selected(self, request):
        """Send selected newsletters directly in batches of 50 recipients."""
        pks = request.data.get('pks', [])
        if not pks:
            return Response({'result': False, 'detail': 'No newsletters selected'}, status=400)

        total_sent = 0
        total_recipients = 0
        errors = []

        for pk in pks:
            result = do_send_newsletter_direct(pk)
            total_sent += result['sent']
            total_recipients += result['total']
            if result['error']:
                errors.append(f'Newsletter #{pk}: {result["error"]}')

        detail = f'{total_sent}/{total_recipients} recipients reached across {len(pks)} newsletter(s)'
        if errors:
            detail += ' | Errors: ' + '; '.join(errors)

        return Response({'result': not errors, 'detail': detail})

    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        """Preview a newsletter (placeholder)."""
        newsletter = self.get_object()
        return Response({
            'subject': newsletter.subject,
            'message': newsletter.message,
        })

    @action(detail=True, methods=['get'])
    def preview_recipients(self, request, pk=None):
        """Preview resolved recipients for a newsletter."""
        newsletter = self.get_object()
        recipients = resolve_all_recipients(newsletter.recipients)
        return Response({
            'recipients': recipients,
            'count': len(recipients),
        })


class NewsLetterTaskManagement(AuthAllPermBaseObjectManagement):
    serializer_class = {
        'list': NewsLetterTaskTableSerializer,
        'create': NewsLetterTaskCreateSerializer,
        'update': NewsLetterTaskCreateSerializer,
        'retrieve': NewsLetterTaskDetailSerializer,
        'get_values_for_update': NewsLetterTaskDetailSerializer,
        'destroy': NewsLetterTaskSerializer,
    }
    perms = {
        'list': [f'{APP_PERM_PREFIX}.view_newslettertask'],
        'create': [f'{APP_PERM_PREFIX}.add_newslettertask'],
        'update': [f'{APP_PERM_PREFIX}.change_newslettertask'],
        'retrieve': [f'{APP_PERM_PREFIX}.view_newslettertask'],
        'get_values_for_update': [f'{APP_PERM_PREFIX}.change_newslettertask'],
        'destroy': [f'{APP_PERM_PREFIX}.delete_newslettertask'],
    }
    queryset = NewsLetterTask.objects.select_related('newsletter')
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['newsletter__subject']
    filterset_class = NewsLetterTaskFilterSet
    ordering_fields = ['send_date', 'status', 'created_at']
    ordering = ('-send_date',)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        task = serializer.instance
        get_backend().schedule(task.pk)

    def perform_update(self, serializer):
        task = self.get_object()
        # Revoke previous schedule if changing
        if task.status in ('pending', 'scheduled'):
            get_backend().revoke(task.pk)
            # Reset status for rescheduling
            task.status = 'pending'
            task.save(update_fields=['status'])

        super().perform_update(serializer)
        task = serializer.instance
        get_backend().schedule(task.pk)

    def perform_destroy(self, instance):
        if instance.status in ('pending', 'scheduled'):
            get_backend().revoke(instance.pk)
        super().perform_destroy(instance)


# =============================================================================
# HTML Views
# =============================================================================

@login_required
def email_notification_view(request):
    """Server-rendered page for email notification management."""
    return render(request, 'async_notification/email_notification.html', {
        'create_form': EmailNotificationForm(prefix='create'),
        'update_form': EmailNotificationForm(prefix='update'),
    })


@login_required
def email_template_view(request):
    """Server-rendered page for email template management."""
    return render(request, 'async_notification/email_template.html', {
        'create_form': EmailTemplateForm(prefix='create'),
        'update_form': EmailTemplateForm(prefix='update'),
    })


@login_required
def newsletter_view(request):
    """Server-rendered page for newsletter management."""
    return render(request, 'async_notification/newsletter.html', {
        'create_form': NewsLetterForm(prefix='create'),
        'update_form': NewsLetterForm(prefix='update'),
    })


@login_required
def newsletter_template_view(request):
    """Server-rendered page for newsletter template management."""
    return render(request, 'async_notification/newsletter_template.html', {
        'create_form': NewsLetterTemplateForm(prefix='create'),
        'update_form': NewsLetterTemplateForm(prefix='update'),
    })


@login_required
def newsletter_task_view(request):
    """Server-rendered page for newsletter task management."""
    return render(request, 'async_notification/newsletter_task.html', {
        'create_form': NewsLetterTaskForm(prefix='create'),
        'update_form': NewsLetterTaskForm(prefix='update'),
    })


# =============================================================================
# Auxiliary Endpoints
# =============================================================================

@login_required
def email_autocomplete_view(request):
    """HTMX endpoint for email recipient autocomplete.

    Searches registered resolvers and the User model.
    Returns an HTML fragment with matching results.
    """
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return HttpResponse('')

    results = RecipientResolverRegistry.search_all(query)

    # Also search users
    user_q = Q()
    for field in ASYNC_NOTIFICATION_USER_LOOKUP_FIELDS:
        user_q |= Q(**{f'{field}__icontains': query})
    users = User.objects.filter(user_q).exclude(email='')[:20]
    for user in users:
        results.append({
            'value': user.email,
            'label': f'{user.get_full_name() or user.username} <{user.email}>',
        })

    return render(request, 'async_notification/_autocomplete_results.html', {
        'results': results,
    })


@login_required
def model_fields_view(request):
    """Return field descriptions for a registered context code.

    If no code is provided, returns fields for all registered contexts.
    Returns HTML fragment when Accept: text/html, otherwise JSON.
    """
    # Accept ContentType PKs (from context_models M2M) or legacy code string
    ct_pks = request.GET.getlist('ct')
    if ct_pks:
        fields = get_fields_for_content_types(ct_pks)
    else:
        code = request.GET.get('code', '').strip()
        if not code:
            from django.contrib.contenttypes.models import ContentType as CT
            ct_pks = CT.objects.values_list('pk', flat=True)
            fields = get_fields_for_content_types(ct_pks)
        else:
            fields = get_fields_for_context(code)

    if fields is None:
        return JsonResponse({'error': 'No fields found'}, status=404)

    accept = request.META.get('HTTP_ACCEPT', '')
    if 'text/html' in accept:
        # Build template-ready structure with {{ var }} syntax
        grouped = {}
        for prefix, field_list in fields.items():
            rendered = []
            for f in field_list:
                rendered.append({
                    'template_var': '{{ %s }}' % f['name'],
                    'type': f['type'],
                    'verbose_name': f['verbose_name'],
                })
            grouped[prefix] = rendered
        return render(request, 'async_notification/_model_tree.html', {
            'grouped_fields': grouped,
        })

    return JsonResponse(fields, safe=False)


@login_required
def upload_image_view(request):
    """Upload an image file and return its URL.

    Accepts optional ``upload_session`` parameter to track the file
    for later reassociation with a real object.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return JsonResponse({'error': 'No file provided'}, status=400)

    upload_session = request.POST.get('upload_session', '')
    ct = ContentType.objects.get_for_model(EmailNotification)
    attached = AttachedFile.objects.create(
        content_type=ct,
        object_id=0,
        file=uploaded_file,
        is_inline=True,
        content_id=upload_session,
    )
    return JsonResponse({'location': attached.file.url})


@login_required
def upload_video_view(request):
    """Upload a video file and return its URL.

    Accepts optional ``upload_session`` parameter to track the file
    for later reassociation with a real object.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return JsonResponse({'error': 'No file provided'}, status=400)

    upload_session = request.POST.get('upload_session', '')
    ct = ContentType.objects.get_for_model(EmailNotification)
    attached = AttachedFile.objects.create(
        content_type=ct,
        object_id=0,
        file=uploaded_file,
        content_id=upload_session,
    )
    return JsonResponse({'location': attached.file.url})


@login_required
def preview_file_view(request, pk):
    """Serve an attached file by its primary key."""
    attached = get_object_or_404(AttachedFile, pk=pk)
    response = HttpResponse(attached.file.read(),
                            content_type='application/octet-stream')
    response['Content-Disposition'] = (
        f'inline; filename="{attached.file.name}"')
    return response


@login_required
def reassociate_files_view(request):
    """Reassociate uploaded files from a temporary session to a real object.

    POST parameters:
        upload_session: The UUID session used during uploads.
        object_id: The ID of the newly created object.
        content_type: The app_label.model string (e.g. 'async_notification.emailnotification').
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    upload_session = request.POST.get('upload_session', '')
    object_id = request.POST.get('object_id', '')
    ct_string = request.POST.get('content_type', '')

    if not all([upload_session, object_id, ct_string]):
        return JsonResponse(
            {'error': 'upload_session, object_id, and content_type required'},
            status=400)

    try:
        app_label, model_name = ct_string.split('.')
        ct = ContentType.objects.get(app_label=app_label, model=model_name)
    except (ValueError, ContentType.DoesNotExist):
        return JsonResponse({'error': 'Invalid content_type'}, status=400)

    updated = AttachedFile.objects.filter(
        content_id=upload_session, object_id=0
    ).update(object_id=object_id, content_type=ct)

    return JsonResponse({'reassociated': updated})


@login_required
def preview_template_view(request):
    """Preview an email template with dummy or real data.

    POST parameters:
        message: The template content to render.
        context_code: Optional registered context code for dummy data.
        base_template: Optional base template key from settings.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    from djgentelella.async_notification.preview import (
        build_dummy_context, build_dummy_context_from_fields, render_preview
    )

    message = request.POST.get('message', '')
    base_template_key = request.POST.get('base_template', '')
    ct_pks = request.POST.getlist('ct_pks')

    context = {}
    if ct_pks:
        from djgentelella.async_notification.introspection import get_fields_for_content_types
        fields_data = get_fields_for_content_types(ct_pks)
        if fields_data:
            context = build_dummy_context_from_fields(fields_data)
    else:
        context_code = request.POST.get('context_code', '')
        if context_code:
            context = build_dummy_context(context_code)

    preview_html = render_preview(message, context, base_template_key or None)
    return JsonResponse({'preview': preview_html})
