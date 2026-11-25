"""A form in several steps, with a progress bar and drafts: :class:`GTWizardView`.

::

    from djgentelella.wizard import GTWizardView, Step

    class EmployeeWizard(LoginRequiredMixin, GTWizardView):
        title = _('New employee')
        model = Employee                 # done() saves one Employee
        draft_storage = 'model'          # or 'session' (the default)
        success_url = reverse_lazy('employee-list')
        steps = [
            Step('personal', PersonalForm, _('Personal data')),
            Step('vehicle', VehicleForm, _('Vehicle'),
                 condition=lambda wizard: wizard.cleaned_value(
                     'personal', 'has_car')),
            Step('documents', DocumentsForm, _('Documents')),
        ]

Each step is a form (a ``GTForm``, a ``ModelForm``...). "Next" validates the
step; "Previous" and "Save draft" keep what was typed without validating it;
"Finish" validates every step that applies once more and calls :meth:`done`
inside one transaction. Everything works with plain ``<form>`` posts: no
javascript is needed to move between steps.

A step with a ``condition`` (a callable taking the view, or a condition of
:mod:`djgentelella.authorization`) is skipped while it does not hold; it can
read the data of the steps before it with :meth:`GTWizardView.cleaned_data_for`.

Files are uploaded in chunks (``FileChunkedUpload`` and its subclasses): the
draft keeps the token of the upload, only an upload of the same user is
accepted, and the upload is deleted once the wizard finishes.

Two hooks are left for the page pipeline: :meth:`GTWizardView.on_step`, after
a step validates, and :meth:`GTWizardView.on_finish`, inside the transaction
of :meth:`GTWizardView.done`.
"""

import copy
import json

from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.forms import ModelForm
from django.forms.models import construct_instance
from django.forms.utils import ErrorDict
from django.http import Http404, HttpResponseRedirect, QueryDict
from django.utils.encoding import force_str
from django.utils.http import urlencode
from django.utils.text import capfirst
from django.utils.translation import gettext as _
from django.views.generic import View
from django.views.generic.base import ContextMixin, TemplateResponseMixin

from djgentelella.authorization import evaluate_condition
from djgentelella.chunked_upload.utils import find_upload
from djgentelella.locking import conflict_message, locked_object, object_version
from djgentelella.models import ChunkedUpload
from djgentelella.widgets.core import upload_token
from djgentelella.widgets.files import FileChunkedUpload
from djgentelella.wizard import conf
from djgentelella.wizard.storage import (
    SessionState, find_draft, new_state, save_draft, user_drafts,
)

__all__ = ['ACTION_FIELD', 'ACTIONS', 'GTWizardView', 'STEP_FIELD', 'Step',
           'WizardConflict']

#: The name of the buttons (``<button name="wizard_action" value="next">``).
ACTION_FIELD = 'wizard_action'
#: The hidden field with the step the posted form belongs to.
STEP_FIELD = 'wizard_step'
NEXT, PREVIOUS, SAVE, FINISH, DISCARD = 'next', 'previous', 'save', 'finish', \
    'discard'
#: ``goto:<step>`` goes back to a step already done (the progress bar).
GOTO = 'goto:'
ACTIONS = (NEXT, PREVIOUS, SAVE, FINISH, DISCARD)


class Step:
    """One step: a name (unique, a form prefix), a form class and a title.

    ``condition`` skips the step while it does not hold: a callable that
    receives the wizard view, or a condition of
    :mod:`djgentelella.authorization` (``{"perm": ...}``, ``{"group": ...}``),
    evaluated for the request and the object the wizard edits.
    """

    def __init__(self, name, form_class, title=None, condition=None,
                 description=''):
        if not name or '|' in name or ':' in name:
            raise ImproperlyConfigured('%r is not a valid step name' % (name,))
        self.name = name
        self.form_class = form_class
        self.title = title if title is not None else capfirst(name.replace('_', ' '))
        self.condition = condition
        self.description = description

    def applies(self, wizard):
        if self.condition is None:
            return True
        if callable(self.condition):
            return bool(self.condition(wizard))
        return evaluate_condition(self.condition, wizard.request,
                                  wizard.get_object())

    def __repr__(self):
        return '<Step %s>' % self.name


class WizardConflict(Exception):
    """Raised inside :meth:`GTWizardView.finish` when the object changed
    since the wizard started (optimistic lock): nothing is saved."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def upload_fields(form):
    """``{name: widget}`` of the fields of ``form`` uploaded in chunks."""
    return {name: field.widget for name, field in form.fields.items()
            if isinstance(field.widget, FileChunkedUpload)}


class GTWizardView(TemplateResponseMixin, ContextMixin, View):
    """A wizard: one form per :class:`Step`, a progress bar and drafts.

    Attributes:

    ``steps``           the :class:`Step` list (or override :meth:`get_steps`)
    ``title``           shown above the progress bar
    ``model``           with it, the default :meth:`done` saves one object
                        of it from every ``ModelForm`` of the steps
    ``draft_storage``   ``'session'`` or ``'model'``; ``None`` reads
                        ``GT_WIZARD_DRAFT_STORAGE``
    ``wizard_key``      names the wizard in the session and in its drafts;
                        by default the dotted path of the view
    ``optimistic_lock`` with an object to edit (:meth:`get_object`), refuse
                        to finish if it changed after the wizard started
    ``success_url``     where :meth:`done` goes by default
    """

    steps = ()
    title = ''
    model = None
    draft_storage = None
    wizard_key = None
    optimistic_lock = False
    success_url = None
    success_message = None
    template_name = 'gentelella/wizard/wizard.html'
    #: The fragment with the progress bar, the form and the buttons.
    body_template_name = 'gentelella/wizard/body.html'
    #: When true, a step that does not validate is shown with its errors by
    #: redirecting to the page (the state remembers which step), instead of
    #: rendering the response of the POST.
    errors_by_redirect = False

    # -- configuration --------------------------------------------------------

    def get_steps(self):
        steps = list(self.steps)
        names = [step.name for step in steps]
        if not steps:
            raise ImproperlyConfigured('%s has no steps' % type(self).__name__)
        if len(set(names)) != len(names):
            raise ImproperlyConfigured('%s repeats a step name' % type(self).__name__)
        return steps

    def get_object(self):
        """The object the wizard edits, or ``None`` to create one."""
        return None

    def get_title(self):
        return self.title

    def get_draft_storage(self):
        storage = self.draft_storage or conf.default_storage()
        if storage not in conf.STORAGES:
            raise ImproperlyConfigured('draft_storage must be one of %s'
                                       % ', '.join(conf.STORAGES))
        return storage

    def uses_model_drafts(self):
        """``'model'`` drafts need a signed-in user: anonymous ones keep
        theirs in the session."""
        user = getattr(self.request, 'user', None)
        return self.get_draft_storage() == 'model' and user is not None and \
            user.is_authenticated

    def get_wizard_key(self):
        key = self.wizard_key or '%s.%s' % (
            type(self).__module__, type(self).__qualname__)
        obj = self.get_object()
        if obj is not None and obj.pk is not None:
            key = '%s:%s' % (key, obj.pk)
        return key[:255]

    def get_action_url(self):
        """Where the form posts."""
        return self.request.path

    def get_page_url(self):
        """The page that shows the wizard, where a post redirects."""
        return self.request.path

    def get_draft_url(self, draft_id):
        """The URL that resumes a model draft."""
        return '%s?%s' % (self.get_page_url(), urlencode({'draft': draft_id}))

    def get_success_url(self):
        if self.success_url is None:
            return self.get_page_url()
        return force_str(self.success_url)

    def get_form_kwargs(self, step):
        """Extra keyword arguments of the form of ``step``."""
        return {}

    def get_form_initial(self, step):
        return {}

    def get_form_instance(self, step):
        """The instance of a ``ModelForm`` step: the object being edited when
        the form is of its model."""
        obj = self.get_object()
        form_model = getattr(getattr(step.form_class, '_meta', None), 'model', None)
        if obj is not None and form_model is not None and isinstance(obj, form_model):
            # A copy: validating a ModelForm writes its data on its instance,
            # and the object must keep its values until done() saves it.
            return copy.copy(obj)
        return None

    # -- state ------------------------------------------------------------------

    def session_state(self):
        if not hasattr(self, '_session_state'):
            self._session_state = SessionState(self.request, self.get_wizard_key())
        return self._session_state

    def load_state(self):
        if getattr(self, 'state', None) is None:
            state = self.session_state().load()
            if state is None:
                state = self.start_state()
                self.state = state
                if state.get('version'):
                    # The version the user starts from: kept from the first
                    # page, not from the first post.
                    self.save_state()
            self.state = state
        return self.state

    def start_state(self):
        state = new_state()
        obj = self.get_object()
        if obj is not None and self.optimistic_lock:
            state['version'] = object_version(obj)
        return state

    def save_state(self):
        self.session_state().save(self.state)

    def clear_state(self):
        self.session_state().clear()
        self.state = None

    # -- steps ------------------------------------------------------------------

    def active_steps(self):
        """The steps that apply, in order; each condition sees only the steps
        before it."""
        if getattr(self, '_active', None) is None:
            self._active = []
            for step in self.get_steps():
                if step.applies(self):
                    self._active.append(step)
            if not self._active:
                raise ImproperlyConfigured('no step of %s applies'
                                           % type(self).__name__)
        return self._active

    def forget_steps(self):
        """Compute :meth:`active_steps` and the cleaned data again (after a
        step's data changed)."""
        self._active = None
        self._cleaned = {}

    def get_step(self, name):
        return next((step for step in self.get_steps() if step.name == name), None)

    def current_step(self):
        state = self.load_state()
        active = self.active_steps()
        by_name = {step.name: step for step in active}
        if state.get('current') in by_name:
            return by_name[state['current']]
        # The step it was at no longer applies: the first one not done.
        for step in active:
            if step.name not in state['valid']:
                return step
        return active[-1]

    def step_index(self, step):
        return [item.name for item in self.active_steps()].index(step.name)

    # -- forms ------------------------------------------------------------------

    def step_data(self, step):
        """The data stored for ``step`` as a ``QueryDict``, with its uploads."""
        state = self.load_state()
        data = QueryDict(mutable=True)
        for name, values in (state['data'].get(step.name) or {}).items():
            data.setlist(name, [str(value) for value in values])
        for name, item in (state['files'].get(step.name) or {}).items():
            data[self.prefixed(step, name)] = json.dumps({'token': item['token']})
        return data

    def prefixed(self, step, name):
        return '%s-%s' % (step.name, name)

    def get_form(self, step, data=None):
        kwargs = {'prefix': step.name, 'initial': self.get_form_initial(step)}
        instance = self.get_form_instance(step)
        if instance is not None:
            kwargs['instance'] = instance
        kwargs.update(self.get_form_kwargs(step))
        if data is not None:
            kwargs['data'] = data
        form = step.form_class(**kwargs)
        self.bind_widgets(form)
        return form

    def bind_widgets(self, form):
        """Give the user to the widgets that take one, and keep chunked
        uploads alive while the wizard runs (they are deleted when it
        finishes)."""
        user = getattr(self.request, 'user', None)
        bind = getattr(form, 'bind_upload_user', None)
        if callable(bind):
            bind(user)
        for field in form.fields.values():
            widget = field.widget
            if not callable(bind) and callable(getattr(widget, 'bind_user', None)):
                widget.bind_user(user)
            if isinstance(widget, FileChunkedUpload):
                widget.consume_upload = False
                if hasattr(widget, 'keep_upload'):
                    widget.keep_upload = False

    def bound_form(self, step):
        return self.get_form(step, self.step_data(step))

    def cleaned_data_for(self, name):
        """The ``cleaned_data`` of the step ``name``, or ``{}`` when it has no
        valid data (or does not exist). For the conditions of the steps
        after it."""
        if not hasattr(self, '_cleaned'):
            self._cleaned = {}
        if name not in self._cleaned:
            state = self.load_state()
            step = self.get_step(name)
            self._cleaned[name] = {}
            if step is not None and name in state['valid']:
                form = self.bound_form(step)
                if form.is_valid():
                    self._cleaned[name] = form.cleaned_data
        return self._cleaned[name]

    def cleaned_value(self, step_name, field, default=None):
        """One value of :meth:`cleaned_data_for`."""
        return self.cleaned_data_for(step_name).get(field, default)

    def form_to_show(self, step):
        """The form of the current step as the page shows it: what was typed
        (bound, without errors unless the step was refused), or empty."""
        state = self.load_state()
        if step.name not in state['data'] and step.name not in state['files']:
            return self.get_form(step)
        form = self.bound_form(step)
        if state.get('errors') == step.name:
            form.is_valid()
            return form
        form.full_clean()
        # Typed but not refused: shown as it was, without errors.
        form._errors = ErrorDict()
        return form

    def store_posted(self, step):
        """Keep what was posted for ``step`` (not validated) and its uploads
        -- only those of the same user; an upload left empty keeps the one
        stored before."""
        state = self.load_state()
        posted = self.request.POST
        prefix = step.name + '-'
        state['data'][step.name] = {
            name: posted.getlist(name) for name in posted
            if name.startswith(prefix)}
        if step.name in state['valid']:
            state['valid'].remove(step.name)
        form = self.get_form(step)
        files = dict(state['files'].get(step.name) or {})
        user = getattr(self.request, 'user', None)
        for name in upload_fields(form):
            key = form.add_prefix(name)
            state['data'][step.name].pop(key, None)
            token = upload_token(posted.get(key))
            if not token:
                continue
            if token.get('actions') == 'delete':
                files.pop(name, None)
            elif isinstance(token.get('token'), str):
                upload = find_upload(token['token'], user)
                if upload is not None:
                    files[name] = {'token': upload.upload_id,
                                   'name': upload.filename}
        if files:
            state['files'][step.name] = files
        else:
            state['files'].pop(step.name, None)
        state['errors'] = None
        self.forget_steps()

    def check_uploads(self):
        """Forget the uploads of the state that no longer exist (expired and
        deleted while the draft waited): their steps have to be done again."""
        state = self.load_state()
        user = getattr(self.request, 'user', None)
        for step_name, files in list(state['files'].items()):
            for name, item in list(files.items()):
                if find_upload(item.get('token'), user) is None:
                    del files[name]
                    if step_name in state['valid']:
                        state['valid'].remove(step_name)
            if not files:
                del state['files'][step_name]

    # -- hooks ------------------------------------------------------------------

    def on_step(self, step, form):
        """Called after ``step`` validates, before moving on. Add errors with
        ``form.add_error()`` to keep the user in the step.

        The point where a page pipeline runs its validations and computations
        for one step.
        """

    def on_finish(self, forms, result):
        """Called inside the transaction of :meth:`done`, with the forms of
        every step that applied and what :meth:`done` returned. An exception
        rolls everything back.

        The point where a page pipeline runs its processes.
        """

    def done(self, forms):
        """Save the result; runs inside a transaction. ``forms`` is
        ``{step name: valid form}`` of the steps that applied, in order.

        Returns a response, or ``None`` to go to :meth:`get_success_url`. By
        default, with :attr:`model`, saves one object from every
        ``ModelForm`` (:meth:`save_object`).
        """
        if self.model is None:
            raise ImproperlyConfigured('%s needs a model or its own done()'
                                       % type(self).__name__)
        self.object = self.save_object(forms)
        return None

    def save_object(self, forms, model=None, instance=None, **values):
        """One object of ``model`` (:attr:`model`) -- the one being edited,
        or a new one -- with the fields of every ``ModelForm`` of that model
        in ``forms`` and ``values``; its many-to-many are saved too."""
        model = model or self.model
        obj = instance if instance is not None else self.get_object()
        if obj is None:
            obj = model()
        model_forms = [form for form in forms.values()
                       if isinstance(form, ModelForm) and form._meta.model is model]
        for form in model_forms:
            construct_instance(form, obj, form._meta.fields, form._meta.exclude)
        for name, value in values.items():
            setattr(obj, name, value)
        obj.save()
        for form in model_forms:
            form.instance = obj
            form._save_m2m()
        return obj

    # -- requests ---------------------------------------------------------------

    def get(self, request, *args, **kwargs):
        draft_id = request.GET.get('draft')
        if draft_id:
            return self.resume(draft_id)
        self.load_state()
        return self.render_to_response(self.get_context_data())

    def resume(self, draft_id):
        """Load a model draft of the user into the session; 404 for a draft
        that is not theirs (or of another Site, or expired)."""
        draft = find_draft(self.request, self.get_wizard_key(), draft_id)
        if draft is None:
            raise Http404(_('No such draft.'))
        state = dict(draft.data)
        state['draft'] = str(draft.pk)
        state['errors'] = None
        self.state = state
        self.check_uploads()
        self.forget_steps()
        self.save_state()
        return HttpResponseRedirect(self.get_page_url())

    def post(self, request, *args, **kwargs):
        state = self.load_state()
        action = request.POST.get(ACTION_FIELD) or NEXT
        if action == DISCARD:
            return self.discard()
        active = self.active_steps()
        by_name = {step.name: step for step in active}
        posted = request.POST.get(STEP_FIELD)
        step = by_name.get(posted) or self.current_step()
        self.store_posted(step)
        if action.startswith(GOTO):
            return self.go_to(step, by_name.get(action[len(GOTO):]))
        if action == PREVIOUS:
            return self.previous(step)
        if action == SAVE:
            return self.save_draft(step)
        form = self.bound_form(step)
        if form.is_valid():
            self.on_step(step, form)
        if not form.is_valid():
            return self.step_invalid(step, form)
        state['valid'].append(step.name)
        self.forget_steps()
        active = self.active_steps()
        names = [item.name for item in active]
        if step.name not in names:
            # Its own data made it not apply (an odd condition): go on from
            # the first step not done.
            state['current'] = None
            step = self.current_step()
            state['current'] = step.name
            self.save_state()
            return self.redirect()
        index = names.index(step.name)
        if action == NEXT and index + 1 < len(active):
            state['current'] = names[index + 1]
            self.save_state()
            return self.redirect()
        return self.finish()

    def redirect(self):
        return HttpResponseRedirect(self.get_page_url())

    def step_invalid(self, step, form):
        state = self.load_state()
        state['current'] = step.name
        if self.errors_by_redirect:
            state['errors'] = step.name
            self.save_state()
            return self.redirect()
        self.save_state()
        return self.render_to_response(self.get_context_data(form=form, step=step))

    def previous(self, step):
        state = self.load_state()
        index = self.step_index(step)
        state['current'] = self.active_steps()[max(index - 1, 0)].name
        self.save_state()
        return self.redirect()

    def go_to(self, step, target):
        """Back to a step before the current one; forward only to steps
        already done, with no step left undone in between."""
        state = self.load_state()
        if target is not None:
            names = [item.name for item in self.active_steps()]
            index, wanted = names.index(step.name), names.index(target.name)
            if wanted <= index or all(name in state['valid']
                                      for name in names[:wanted]):
                state['current'] = target.name
        self.save_state()
        return self.redirect()

    def save_draft(self, step):
        """Keep the wizard to go on later: in the session, or as a
        :class:`~djgentelella.models.WizardDraft` of the user."""
        state = self.load_state()
        state['current'] = step.name
        if self.bound_form(step).is_valid():
            state['valid'].append(step.name)
        if self.uses_model_drafts():
            draft = save_draft(self.request, self.get_wizard_key(), state,
                               self.draft_title(step))
            self.save_state()
            messages.success(self.request, _(
                'Draft saved. You can go on with it later from this page.'),
                fail_silently=True)
            return HttpResponseRedirect(self.get_draft_url(draft.pk))
        self.save_state()
        messages.success(self.request, _(
            'Draft saved in this session. Come back to this page to go on.'),
            fail_silently=True)
        return self.redirect()

    def draft_title(self, step):
        title = self.get_title()
        return '%s - %s' % (title, step.title) if title else str(step.title)

    def discard(self):
        state = self.load_state()
        if state.get('draft'):
            draft = find_draft(self.request, self.get_wizard_key(), state['draft'])
            if draft is not None:
                draft.delete()
        self.clear_state()
        messages.info(self.request, _('The wizard was discarded.'),
                      fail_silently=True)
        return self.redirect()

    def finish(self):
        """Validate every step that applies and, in one transaction, check
        the object version, :meth:`done` and :meth:`on_finish`."""
        state = self.load_state()
        forms = {}
        for step in self.active_steps():
            form = self.bound_form(step)
            if not form.is_valid():
                if step.name in state['valid']:
                    state['valid'].remove(step.name)
                return self.step_invalid(step, form)
            forms[step.name] = form
        last = self.active_steps()[-1]
        key = self.get_wizard_key()
        try:
            with transaction.atomic():
                self.check_version()
                response = self.done(forms)
                self.on_finish(forms, response)
        except WizardConflict as conflict:
            form = forms[last.name]
            form.add_error(None, conflict.message)
            self.conflict = True
            if self.errors_by_redirect:
                state['current'] = last.name
                state['errors'] = None
                self.save_state()
                messages.error(self.request, conflict.message, fail_silently=True)
                return self.redirect()
            return self.render_to_response(self.get_context_data(form=form,
                                                                 step=last))
        self.finished(state, key)
        if response is None:
            if self.success_message:
                messages.success(self.request, self.success_message,
                                 fail_silently=True)
            response = HttpResponseRedirect(self.get_success_url())
        return response

    def check_version(self):
        """Raise :class:`WizardConflict` if the object being edited changed
        since the wizard started (``optimistic_lock``); the row stays locked
        until the transaction ends."""
        obj = self.get_object()
        state = self.load_state()
        if obj is None or not self.optimistic_lock or not state.get('version'):
            return
        fresh = locked_object(obj)
        if fresh is None or object_version(fresh) != state['version']:
            raise WizardConflict(conflict_message(fresh))

    def finished(self, state, key):
        """After a successful :meth:`done`: delete its uploads, its draft and
        its state."""
        tokens = [item['token'] for step in self.active_steps()
                  for item in (state['files'].get(step.name) or {}).values()]
        if state.get('draft'):
            draft = find_draft(self.request, key, state['draft'])
            if draft is not None:
                draft.delete()
        if tokens:
            for upload in ChunkedUpload.objects.filter(upload_id__in=tokens):
                upload.delete()
        self.clear_state()

    # -- rendering --------------------------------------------------------------

    def wizard_context(self, form=None, step=None):
        """What ``gentelella/wizard/body.html`` renders."""
        state = self.load_state()
        step = step or self.current_step()
        if form is None:
            form = self.form_to_show(step)
        if state.get('errors') == step.name:
            state['errors'] = None
            self.save_state()
        active = self.active_steps()
        index = self.step_index(step)
        items = []
        for position, item in enumerate(active):
            done = item.name in state['valid']
            items.append({
                'name': item.name, 'title': item.title, 'number': position + 1,
                'done': done, 'current': item.name == step.name,
                'reachable': item.name != step.name and (
                    position < index or all(other.name in state['valid']
                                            for other in active[:position]))})
        files = state['files'].get(step.name) or {}
        uploaded = [{'field': form.fields[name].label or name, 'name': item['name']}
                    for name, item in files.items() if name in form.fields]
        drafts = []
        if self.uses_model_drafts():
            drafts = [{'title': draft.title or draft.key, 'updated': draft.updated_at,
                       'url': self.get_draft_url(draft.pk),
                       'current': str(draft.pk) == str(state.get('draft'))}
                      for draft in user_drafts(self.request,
                                               self.get_wizard_key())[:20]]
        return {
            'title': self.get_title(),
            'steps': items,
            'step': step,
            'number': index + 1,
            'total': len(active),
            'percent': int(round(100 * (index + 1) / len(active))),
            'form': form,
            'is_first': index == 0,
            'is_last': index == len(active) - 1,
            'action_url': self.get_action_url(),
            'step_field': STEP_FIELD,
            'action_field': ACTION_FIELD,
            'uploaded': uploaded,
            'drafts': drafts,
            'draft_id': state.get('draft'),
            'started': bool(state['data'] or state['files']),
            'conflict': getattr(self, 'conflict', False),
            'multipart': form.is_multipart(),
        }

    def get_context_data(self, form=None, step=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context['wizard'] = self.wizard_context(form, step)
        context['wizard_body_template'] = self.body_template_name
        context['view'] = self
        return context
