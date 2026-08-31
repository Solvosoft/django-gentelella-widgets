from datetime import datetime, time

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_POST

from demoapp.calendar.forms import CalendarModelform
from demoapp.models import Calendar, Event


def calendar_view(request):
    form = CalendarModelform(initial={'options': '{}'})
    if request.method == 'POST':
        form = CalendarModelform(request.POST, initial={'options': '{}'})
        if form.is_valid():
            form.save()
            messages.success(request, 'Form submitted succesfully')
    return render(request, 'gentelella/index.html', {'form': form})


def _parse_start(start_raw):
    """dateClick's dateStr is date-only ("2026-08-19"); the add/edit modal's
    own "YYYY-MM-DDTHH:MM" is what parse_datetime wants directly, but a
    caller that skips the time field still needs the date-only fallback."""
    start = parse_datetime(start_raw)
    if start is None:
        start_date = parse_date(start_raw)
        start = datetime.combine(start_date, time.min) if start_date else None
    if start is not None and timezone.is_naive(start):
        start = timezone.make_aware(start)
    return start


def _event_json(event):
    return {
        'id': str(event.pk),
        'title': event.title,
        'start': event.start.isoformat(),
        'color': event.color,
        'description': event.description,
    }


@require_POST
def event_create(request):
    """Answers CalendarInput's add-event modal with what FullCalendar expects
    back: {id, title, start, color, description}."""
    title = request.POST.get('title', '').strip()
    start_raw = request.POST.get('start')
    color = request.POST.get('color') or None
    description = request.POST.get('description', '').strip() or None
    if not title or not start_raw:
        return JsonResponse({'error': 'title and start are required'}, status=400)

    start = _parse_start(start_raw)
    if start is None:
        return JsonResponse({'error': 'invalid start'}, status=400)

    calendar, _created = Calendar.objects.get_or_create(title='Demo')
    event = Event.objects.create(
        calendar=calendar, title=title, start=start, color=color,
        description=description)
    return JsonResponse(_event_json(event))


@require_POST
def event_update(request):
    """Answers CalendarInput's edit modal the same shape event_create does,
    so the JS can reuse one success handler shape for both."""
    event = get_object_or_404(Event, pk=request.POST.get('id'))
    title = request.POST.get('title', '').strip()
    start_raw = request.POST.get('start')
    if not title or not start_raw:
        return JsonResponse({'error': 'title and start are required'}, status=400)

    start = _parse_start(start_raw)
    if start is None:
        return JsonResponse({'error': 'invalid start'}, status=400)

    event.title = title
    event.start = start
    event.color = request.POST.get('color') or None
    event.description = request.POST.get('description', '').strip() or None
    event.save(update_fields=['title', 'start', 'color', 'description'])
    return JsonResponse(_event_json(event))


@require_POST
def event_delete(request):
    event = get_object_or_404(Event, pk=request.POST.get('id'))
    event.delete()
    return JsonResponse({'ok': True})
