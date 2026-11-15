"""Small helpers shared by the engine, the actions and the JSON loader."""

import json
from datetime import datetime, timedelta

from django.core.exceptions import ImproperlyConfigured
from django.core.files import File
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.dateparse import parse_datetime, parse_duration


class LogEncoder(DjangoJSONEncoder):
    """DjangoJSONEncoder (ISO dates, decimals, UUIDs) that never fails:
    files become their name, anything else its text."""

    def default(self, value):
        if isinstance(value, File):
            return value.name
        if isinstance(value, timedelta):
            return str(value)
        try:
            return super().default(value)
        except TypeError:
            return str(value)


def json_safe(data):
    """``data`` as plain JSON, for the log, the variables and task data."""
    return json.loads(json.dumps(data, cls=LogEncoder))


def to_timedelta(value):
    """A duration: a ``timedelta``, seconds, or text Django parses -- ISO 8601
    (``"P2D"``, ``"PT4H"``) or ``"2 days, 4:00:00"``."""
    if value is None or isinstance(value, timedelta):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return timedelta(seconds=value)
    if isinstance(value, str):
        parsed = parse_duration(value)
        if parsed is not None:
            return parsed
    raise ImproperlyConfigured('%r is not a duration' % (value,))


def to_datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed is not None:
            return parsed
    raise ValueError('%r is not a date and time' % (value,))


def value_at(obj, path):
    """``obj.a.b.c`` for ``path='a.b.c'``; None as soon as one is missing."""
    for part in path.split('.'):
        if obj is None:
            return None
        obj = obj.get(part) if isinstance(obj, dict) else getattr(obj, part, None)
    return obj
