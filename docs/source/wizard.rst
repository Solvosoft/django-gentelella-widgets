======
Wizard
======

*(Asistente de varios pasos con borrador.)* A long form -- hiring an
employee, a request with several sections -- split in steps, with a progress
bar, "Previous" without losing what was typed, and a **draft** to go on later.
Two ways to use it: in code, a view (``GTWizardView``), and in a design, the
``wizard`` component (``djgentelella.designs``).

It is a plain module of ``djgentelella``: nothing to add to
``INSTALLED_APPS``. Its only model, ``WizardDraft``, lives in
``djgentelella/models.py`` and migrates with ``djgentelella``
(``0025_wizarddraft``).


A wizard in code
================

.. code:: python

    from django.contrib.auth.mixins import LoginRequiredMixin
    from djgentelella.wizard import GTWizardView, Step

    class EmployeeWizard(LoginRequiredMixin, GTWizardView):
        title = _('New employee')
        model = NewHire                  # done() saves one NewHire
        draft_storage = 'model'          # or 'session' (the default)
        success_url = reverse_lazy('employee_wizard')
        success_message = _('The employee was saved.')
        steps = [
            Step('personal', PersonalForm, _('Personal data')),
            Step('vehicle', VehicleForm, _('Vehicle'),
                 condition=lambda wizard: wizard.cleaned_value('personal',
                                                               'has_car')),
            Step('job', JobForm, _('Job')),
        ]

    # urls.py
    path('wizard/employee/', EmployeeWizard.as_view(), name='employee_wizard')

Each ``Step`` has a name (unique; it is the form's prefix), a form class -- a
``GTForm``, usually a ``ModelForm`` -- a title, an optional ``description``
and an optional ``condition``. The demo has this one at ``/wizard/employee/``
(``demo/demoapp/wizard/``).

The buttons
-----------

=================  ==========================================================
button             what it does
=================  ==========================================================
Next               validates the step; with errors it stays, otherwise it
                   goes to the next step that applies
Previous           keeps what was typed (errors are not shown) and goes
                   back
a step of the bar  goes back to that step, or forward to one whose previous
                   steps are all done
Save draft         keeps what was typed and saves the draft (see below)
Finish             on the last step: validates **every** step that applies
                   once more and runs ``done()`` in one transaction
Discard            forgets the state and deletes its draft
=================  ==========================================================

Everything is a plain ``<form method="post">``: no javascript is needed to
move between steps. The first submit button of the form is a hidden "Next"
(or "Finish"), so Enter never goes back. The progress bar is a Bootstrap 5
``progress`` with ``role="progressbar"`` and ``aria-valuenow``; the steps are
an ordered list with ``aria-current="step"``.

Conditional steps
-----------------

A step with a ``condition`` is skipped while it does not hold:

* a callable that receives the view: it reads the earlier steps with
  ``wizard.cleaned_data_for('personal')`` or
  ``wizard.cleaned_value('personal', 'has_car')`` (``{}``/``None`` while that
  step has no valid data);
* or a condition of :doc:`authorization` (``{"perm": ...}``, ``{"group": ...}``,
  ``{"flag": ...}``), evaluated for the request and the object being edited.

The steps that apply are computed on every request, in order. The data of a
step that stops applying is kept in the state (it comes back if the step
does) but is **not** given to ``done()``.

Finishing
---------

``done(forms)`` receives ``{step name: valid form}`` of the steps that apply,
in order, inside ``transaction.atomic()``. It returns a response, or ``None``
to go to ``get_success_url()``. With ``model`` set, the default ``done()``
calls ``save_object(forms)``: one object -- the one being edited, or a new
one -- with the fields of every ``ModelForm`` of that model, plus their
many-to-many. ``save_object(forms, **values)`` sets other fields too (the
demo sets ``site_id``). An exception in ``done()`` rolls everything back and
keeps the state, so the user can try again.

Editing an object
-----------------

Return it from ``get_object()``: every ``ModelForm`` step gets (a copy of) it
as its instance, the wizard key includes its pk, and ``done()`` saves it.
With ``optimistic_lock = True`` the version of the object
(:doc:`locking`) is taken when the wizard starts; when it finishes, the row is
locked (``select_for_update``) and, if its version changed, nothing is saved
and the last step shows the conflict. "Discard" starts again from the current
data.

Hooks
-----

``on_step(step, form)``
    whenever the data of ``step`` validates: on "Next", quietly on
    "Previous", "Save draft" and the steps of the bar, and for every step once
    more on "Finish" -- it may run more than once per step, so no side effects
    that cannot repeat. ``form.add_error()`` keeps the user in the step.
``on_finish(forms, result)``
    inside the transaction of ``done()``, with what it returned; an exception
    rolls everything back.

These are where a page pipeline runs its validations and computations per
step and its processes at the end.

Other hooks: ``get_steps()``, ``get_form_kwargs(step)``,
``get_form_initial(step)``, ``get_form_instance(step)``, ``get_wizard_key()``,
``get_title()``, ``get_page_url()``, ``get_action_url()``,
``get_success_url()``. ``template_name`` is ``gentelella/wizard/wizard.html``
(it extends ``gentelella/base.html``) and ``body_template_name``
``gentelella/wizard/body.html``, the bar, the form and the buttons, which a
template of your own can ``{% include %}`` with the ``wizard`` context.


State and drafts
================

The state of a wizard in progress always lives in the **session**, one slot
per wizard, Site and user: the step the user is at, what was posted for each
step and the uploads. **What is posted is kept, not** ``cleaned_data``:
cleaned values (rows, decimals, files) are not JSON, and validating every
step again at the end catches what changed meanwhile -- a related row
deleted, a choice no longer offered.

"Save draft" keeps it:

``draft_storage = 'session'`` (the default, ``GT_WIZARD_DRAFT_STORAGE``)
    in the session itself: coming back to the page goes on where it was.
``draft_storage = 'model'``
    also as a ``WizardDraft`` row (user, Site, wizard key, title, data,
    uploads, updated), which survives the session. The page lists the user's
    drafts of that wizard; ``?draft=<id>`` resumes one. A draft is only ever
    found for its own user and Site: any other id is a **404**. An anonymous
    user's drafts stay in the session.

Drafts **expire** ``GT_WIZARD_DRAFT_EXPIRATION`` after their last change (a
``timedelta`` or a number of days; 30 days by default): an expired draft is
not listed nor resumed, the session state is dropped, and

.. code:: bash

    python manage.py delete_expired_wizard_drafts [--dry-run]

deletes the rows (run it from cron, next to ``delete_expired_uploads``).

Files
-----

A file of a wizard is uploaded **in chunks** (``FileChunkedUpload``,
``UserFileChunkedUpload``, ``PDFViewerWidget``): a draft keeps the token of
the upload, never the file. Only a finished upload **of the same user** is
taken (``chunked_upload.utils.find_upload``); another user's token is
ignored. While the wizard runs the upload is not deleted
(``FileChunkedUpload.consume_upload = False`` on its forms): it is validated
on every step and once more at the end, and deleted when ``done()`` commits.
The page says which file is already uploaded; posting the step without a new
one keeps it. A plain ``FileInput`` cannot be kept by a draft.

``delete_expired_uploads`` leaves alone the uploads a live ``WizardDraft``
keeps (``WizardDraft.uploads``). A session draft cannot protect its uploads
that way: they expire with ``CHUNKED_UPLOAD_EXPIRATION_DELTA`` (one day by
default), and when a draft is resumed an upload that no longer exists is
forgotten, so its step has to be done again.


The ``wizard`` design component
===============================

.. code:: json

    {"type": "wizard", "id": "hire", "props": {
        "model": "demoapp.NewHire",
        "title": "Hire an employee",
        "site_field": "site",
        "draft": "model",
        "steps": [
            {"name": "personal", "title": "Personal data",
             "fields": ["name", "email", "birth_date", "has_car"],
             "widgets": {"has_car": "YesNoInput"}},
            {"name": "vehicle", "title": "Vehicle", "fields": ["car_plate"],
             "when": {"field": "has_car", "equals": true}},
            {"name": "job", "title": "Job",
             "fields": ["department", "start_date", "contract"],
             "condition": {"perm": "demoapp.change_newhire"}}],
        "success_message": "The employee was hired."}}

=====================  ======================================================
prop                   meaning
=====================  ======================================================
``model``              an exposed model; every step is a form of it
``steps``              each with ``name`` (``[a-z][a-z0-9_]*``), ``title``,
                       ``description``, ``fields`` and, as an entry of the
                       design's ``forms``, ``render``, ``grid``, ``widgets``
                       and ``help``; plus ``condition`` and ``when``
``mode``               ``create`` (default) or ``edit``: the object of a page
                       about one ``model`` (``meta.parent``)
``perms``              ``{"create": [...], "update": [...]}``; by default the
                       model's ``add`` / ``change``
``site_field``         a foreign key to ``sites.Site``: set to the current
                       Site on creation; an object of another Site cannot be
                       edited
``draft``              ``session`` or ``model`` (``GT_WIZARD_DRAFT_STORAGE``)
``optimistic_lock``    edit mode: refuse to finish if the object changed
``success_url``        ``page:<path>`` or a URL name without arguments; empty:
                       the page itself
``success_message``    the message when it finishes (default "Saved.")
``title``              above the progress bar
=====================  ======================================================

``when`` skips a step by a value of a field of an **earlier** step:
``{"field": "has_car", "equals": true}``, ``{"field": "kind", "in": ["a",
"b"]}`` or ``{"field": "notes", "filled": true}``. The value compared is the
cleaned one, as JSON has it: a row by its pk, a date or a decimal as text.
``condition`` is a condition of :doc:`authorization`, evaluated with the
object in edit mode. A step with both needs both.

``resolve()`` checks: fields the exposure allows, each field in one step
only, the ``site_field`` in none, every field the model requires (not
``blank``, without default) in some step on creation, ``when`` over an
earlier step, valid conditions and permissions, ``mode: "edit"`` only on a
page about the model, ``optimistic_lock`` only in edit mode, and a file field
uploaded in chunks -- it gets ``FileChunkedUpload`` unless ``widgets`` says
another upload widget.

How it is served: the page renders the current step; the form posts to the
node's endpoint (``gtapis/designs/<page>/<node>/``, plus ``<pk>/`` in edit
mode), which answers with a redirect to the page -- also when the step has
errors: the state remembers which step to show with its errors, once
(post/redirect/get). ``GET <endpoint>?draft=<id>`` resumes a model draft. The
endpoint checks CSRF (also for anonymous users), the permissions (403), the
node's condition (404), in edit mode the ``view`` permission of the model and
the Site of the object (404).

The demo publishes ``employee_wizard`` at ``/designs/employees/new/`` (with
model drafts and a contract uploaded in chunks) and ``employee_edit`` at
``/designs/employees/edit/<pk>`` (edit mode with the optimistic lock).

Hints for the editor (``x-widget``)
-----------------------------------

The props schema reuses ``model``, ``model-field`` (``site_field`` with
``x-filter: site``; ``when.field``), ``model-fields`` (each step's
``fields``), ``widgets``, ``condition``, ``perms`` and ``link``
(``success_url``), and adds:

``wizard-steps``
    the ``steps`` list: an ordered list of steps, each a small form editor
    (fields of the model, layout, widgets, help) with its ``condition`` and
    ``when``;
``step-when``
    the ``when`` of a step: a field of an earlier step, an operator
    (``equals``, ``in``, ``filled``) and its value;
``form-grid`` and ``help``
    a step's ``grid`` and ``help``, as in the design's ``forms``.


Settings
========

``GT_WIZARD_DRAFT_EXPIRATION``
    how long a draft lives after its last change; ``timedelta`` or days.
    Default: 30 days.
``GT_WIZARD_DRAFT_STORAGE``
    ``'session'`` (default) or ``'model'``, for the views and components that
    do not say.
