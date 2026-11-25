"""Send feedback, the reviewers' inbox and one feedback with its answer."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from djgentelella.feedback.conf import feedback_enabled
from djgentelella.feedback.forms import FeedbackForm, ResponseForm
from djgentelella.models import Feedback
from djgentelella.notification import create_notification
from djgentelella.sites import get_current_site, site_q

REVIEW = 'djgentelella.view_feedback'
ANSWER = 'djgentelella.change_feedback'


def _wants_json(request):
    return 'application/json' in request.headers.get('Accept', '') or \
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _back(request):
    target = request.POST.get('next') or ''
    if target and url_has_allowed_host_and_scheme(
            target, allowed_hosts={request.get_host()},
            require_https=request.is_secure()):
        return target
    try:
        return reverse('home')
    except NoReverseMatch:
        return '/'


@login_required
@require_POST
def feedback_create(request):
    """Store the feedback of the button. 404 when the feedback is off for
    the request (setting, Site or anonymous user)."""
    if not feedback_enabled(request):
        raise Http404()
    form = FeedbackForm(request.POST, prefix='gtfeedback')
    if not form.is_valid():
        if _wants_json(request):
            return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
        messages.error(request, _('The feedback could not be sent: %(errors)s') % {
            'errors': '; '.join(' '.join(errors) for errors in form.errors.values())})
        return HttpResponseRedirect(_back(request))
    feedback = form.save(commit=False)
    feedback.user = request.user
    feedback.site = get_current_site(request)
    feedback.save()
    message = _('Thank you: your feedback was sent.')
    if _wants_json(request):
        return JsonResponse({'ok': True, 'id': feedback.pk, 'message': message})
    messages.success(request, message)
    return HttpResponseRedirect(_back(request))


def reviewer_queryset(request):
    """The feedback a reviewer of the request's Site sees: that Site's and
    the global one."""
    return Feedback.objects.filter(site_q(get_current_site(request))).select_related(
        'user', 'site', 'responded_by')


@login_required
@permission_required(REVIEW, raise_exception=True)
def feedback_inbox(request):
    """The reviewers' inbox, newest first, filtered by status and type."""
    queryset = reviewer_queryset(request)
    status = request.GET.get('status', '')
    if status in dict(Feedback.STATUSES):
        queryset = queryset.filter(status=status)
    kind = request.GET.get('kind', '')
    if kind in dict(Feedback.KINDS):
        queryset = queryset.filter(kind=kind)
    page = Paginator(queryset, 25).get_page(request.GET.get('page'))
    return render(request, 'gentelella/feedback/inbox.html', {
        'page': page, 'status': status, 'kind': kind,
        'statuses': Feedback.STATUSES, 'kinds': Feedback.KINDS,
    })


def notify_author(request, feedback):
    """Tell the author that their feedback was answered."""
    if feedback.user is None:
        return
    create_notification(
        _('Your feedback was answered: %(text)s') % {'text': feedback.text[:80]},
        feedback.user, 'info',
        link=request.build_absolute_uri(reverse('gt_feedback_detail',
                                                args=[feedback.pk])),
        request=request)


@login_required
def feedback_detail(request, pk):
    """One feedback: its author reads it with the answer; a reviewer of its
    Site also changes its status and answers it."""
    user = request.user
    reviewer = user.has_perm(REVIEW) or user.has_perm(ANSWER)
    queryset = Feedback.objects.select_related('user', 'site', 'responded_by')
    if reviewer:
        queryset = queryset.filter(Q(site_q(get_current_site(request))) | Q(user=user))
    else:
        queryset = queryset.filter(user=user)
    feedback = get_object_or_404(queryset, pk=pk)
    can_answer = user.has_perm(ANSWER) and reviewer_queryset(request).filter(
        pk=feedback.pk).exists()
    form = None
    if can_answer:
        before = feedback.response
        form = ResponseForm(request.POST or None, instance=feedback, prefix='answer')
        if request.method == 'POST' and form.is_valid():
            feedback = form.save(commit=False)
            answered = feedback.response.strip() and feedback.response != before
            if answered:
                feedback.responded_by = user
                feedback.responded_at = timezone.now()
                if feedback.status in (Feedback.NEW, Feedback.REVIEWING):
                    feedback.status = Feedback.ANSWERED
            feedback.save()
            if answered:
                notify_author(request, feedback)
            messages.success(request, _('Feedback saved.'))
            return redirect('gt_feedback_detail', pk=feedback.pk)
    elif request.method == 'POST':
        raise Http404()
    return render(request, 'gentelella/feedback/detail.html', {
        'feedback': feedback, 'form': form,
        'inbox': user.has_perm(REVIEW),
    })
