"""Where a wizard keeps its state between requests, and its drafts.

The state of a wizard in progress is a JSON dict::

    {"v": 1,
     "current": "contact",                 # the step the user is at
     "data": {"personal": {"personal-name": ["Ana"], ...}},  # what was posted
     "valid": ["personal"],                # steps whose data validated
     "files": {"personal": {"cv": {"token": "...", "name": "cv.pdf"}}},
     "errors": null,                       # step to show with its errors
     "draft": null,                        # id of its WizardDraft, if any
     "version": null,                      # object version (optimistic lock)
     "updated": "2026-11-25T10:00:00+00:00"}

It always lives in the session, under one slot per wizard, Site and user.
"Save draft" keeps it there (``session`` drafts) or copies it to a
:class:`~djgentelella.models.WizardDraft` row (``model`` drafts), which
survives the session and is resumed by its id. Neither is ever read for
another user or another Site.

**What is posted, not ``cleaned_data``:** the data of each step is kept as it
was submitted (lists of strings), and every step is validated again when the
wizard finishes. Cleaned values -- model instances, ``Decimal``, files -- are
not JSON, and validating again at the end catches what changed meanwhile (a
related row deleted, a choice no longer offered).
"""

import uuid

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from djgentelella.models import WizardDraft
from djgentelella.sites import get_current_site, site_pk
from djgentelella.wizard.conf import expired_before

__all__ = ['SESSION_KEY', 'STATE_VERSION', 'SessionState', 'draft_uploads',
           'find_draft', 'new_state', 'save_draft', 'state_expired',
           'user_drafts']

SESSION_KEY = 'gt_wizard'
STATE_VERSION = 1


def new_state():
    return {'v': STATE_VERSION, 'current': None, 'data': {}, 'valid': [],
            'files': {}, 'errors': None, 'draft': None, 'version': None,
            'updated': timezone.now().isoformat()}


def touch(state):
    state['updated'] = timezone.now().isoformat()
    return state


def state_expired(state, now=None):
    """Whether ``state`` was last changed before the drafts expire."""
    updated = parse_datetime(str(state.get('updated') or ''))
    return updated is None or updated < expired_before(now)


def valid_state(state):
    """``state`` if it has the shape this version writes, else ``None``."""
    if not isinstance(state, dict) or state.get('v') != STATE_VERSION:
        return None
    for name, kind in (('data', dict), ('valid', list), ('files', dict)):
        if not isinstance(state.get(name), kind):
            return None
    return state


def user_key(request):
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        return str(user.pk)
    return 'anonymous'


class SessionState:
    """The state of one wizard for the session of ``request``."""

    def __init__(self, request, key):
        self.request = request
        self.slot = '%s|%s|%s' % (key, site_pk(get_current_site(request)) or '',
                                  user_key(request))

    def _all(self):
        return self.request.session.get(SESSION_KEY) or {}

    def load(self):
        state = valid_state(self._all().get(self.slot))
        if state is not None and state_expired(state):
            self.clear()
            return None
        return state

    def save(self, state):
        everything = dict(self._all())
        everything[self.slot] = touch(state)
        self.request.session[SESSION_KEY] = everything
        self.request.session.modified = True

    def clear(self):
        everything = dict(self._all())
        if everything.pop(self.slot, None) is not None:
            self.request.session[SESSION_KEY] = everything
            self.request.session.modified = True


def user_drafts(request, key):
    """The live drafts of ``key`` of the request's user in its Site."""
    return WizardDraft.objects.of(getattr(request, 'user', None),
                                  get_current_site(request)).live().filter(key=key)


def find_draft(request, key, draft_id):
    """The live draft ``draft_id`` of ``key`` that belongs to the request's
    user in its Site, or ``None`` -- whoever else it belongs to."""
    try:
        draft_id = uuid.UUID(str(draft_id))
    except (TypeError, ValueError, AttributeError):
        return None
    try:
        return user_drafts(request, key).filter(pk=draft_id).first()
    except ValidationError:
        return None


def draft_uploads(state):
    """``upload_id`` of every chunked upload ``state`` keeps."""
    return sorted({item['token'] for files in state.get('files', {}).values()
                   for item in files.values()
                   if isinstance(item, dict) and item.get('token')})


def save_draft(request, key, state, title=''):
    """Create or update the :class:`WizardDraft` of ``state``; returns it.

    The draft named by ``state["draft"]`` is updated only when it is one of
    the user's; otherwise a new one is created.
    """
    draft = find_draft(request, key, state.get('draft')) if state.get('draft') \
        else None
    if draft is None:
        draft = WizardDraft(user=request.user, site_id=site_pk(
            get_current_site(request)), key=key)
    state['draft'] = str(draft.pk)
    data = dict(touch(state))
    data['errors'] = None
    draft.data = data
    draft.title = str(title)[:255]
    draft.uploads = draft_uploads(state)
    draft.save()
    return draft
