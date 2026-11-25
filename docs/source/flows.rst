Flows
=====

A flow moves one object through **activities**. The simplest ones are
**states** left by **transitions**, each with its permissions, an optional
condition, an optional form and **actions** (assign, notify, email, set a
field, call a function...). Beside them a flow may have switches, waits,
parallel branches, subflows, human tasks and automatic actions.

Where an object stands is kept apart from its model, in ``FlowInstance``,
together with the instance **variables**, its status and the version of the
flow it started with. An object that has no instance yet is in the flow's
``initial`` state, and one model can go through several flows.

Installation
------------

``djgentelella.flows`` is a Django app of its own (label ``gtflows``) and needs
``django.contrib.sites``:

.. code:: python

    INSTALLED_APPS = [
        ...
        'djgentelella',
        'django.contrib.sites',
        'djgentelella.flows',
    ]
    SITE_ID = 1

then ``python manage.py migrate``. djgentelella's URLs include the flow pages
only when the app is installed. ``djgentelella.flows`` imports nothing while
the app registry loads: ``from djgentelella.flows import Flow`` works anywhere
once Django is set up, but never import it from another app's ``models.py``.

Declaring a flow
----------------

Write it in ``<app>/gtflows.py``. The app imports that module when the
registry is ready (``FlowsConfig.ready()``), so flows also exist in Celery
workers and management commands, not only behind the URLconf.

.. code:: python

    from djgentelella.flows import (Assign, Flow, Notify, SendEmail, SetField,
                                    Transition, register_flow)

    @register_flow
    class ArticleReviewFlow(Flow):
        title = 'Article review'
        model = Article
        states = [('draft', 'Draft'), ('review', 'In review'),
                  ('published', 'Published')]
        initial = 'draft'
        transitions = [
            Transition('submit', 'draft', 'review', label='Submit',
                       perms=['news.change_article'],
                       actions=[Assign(group='Editors')]),
            Transition('publish', 'review', 'published', label='Publish',
                       perms=['news.publish_article'], form=PublishForm,
                       condition=lambda context: context.obj.author != context.user,
                       actions=[Notify('{{ object }} is out.', to='field:author'),
                                SendEmail('article_published', to=['editors@group.local'])]),
        ]

The registry name is ``<app_label>.<ClassName>``, ``news.ArticleReviewFlow``
here. Set ``name`` to choose another. ``source`` may be a state, a list of
states, or ``'*'``, which means any state except the transition's own target
and the flow's ``final_states``.

``final_states`` lists the states no transition leaves. If you leave it out, a
state counts as final when no transition can leave it, ``'*'`` included. When
every token of an instance rests in a final state, the instance is
**completed**: it leaves the inbox and runs no more timers.

By default a transition **clears the assignment** of the object, unless one
of its actions assigns it again or it has ``keep_assignment=True``.
``log_exclude=['password']`` keeps form fields out of the log.

Conditions
----------

A condition gets the **context** of the run (an ``ActionContext``):
``context.obj``, ``context.user`` (``None`` for the system),
``context.variables``, ``context.data`` (the form data), ``context.flow``,
``context.instance``. It returns true or false, or raises
``TransitionBlocked('...')`` to say why not: the text is shown on the disabled
button and as the error when the transition is refused.

It can be a callable, the name of a function registered with
``register_condition`` (or a dotted path), and -- in JSON definitions --
``{"function": "<name>"}``. Any other dict is a condition of
:doc:`authorization` (``{"perm": ...}``, ``{"all": [...]}``). It is evaluated
for the request when there is one; otherwise -- the usual case in a flow --
for ``context.user`` on ``context.site``, and the system (``user=None``)
counts as an anonymous user, so ``{"perm": ...}`` is false for it.
``publish_definition`` refuses a definition whose conditions are invalid,
unknown authorizations included; a definition already stored still loads, and
a condition naming an authorization that is gone is false.

.. code:: python

    from djgentelella.flows import register_condition

    @register_condition('expenses.is_large')
    def is_large(context):
        return context.obj.amount >= 1000

When a transition runs
----------------------

``flow.run(obj, 'publish', user, form=form, comment='')`` refuses with
``TransitionNotAllowed`` unless all of these hold:

* the instance is running (not suspended, completed or terminated);
* one of the activities it waits in is a source of the transition;
* the user has **all** of its ``perms``;
* its ``condition`` holds, when it has one.

When it does run, it does the following in **one transaction**, so an action
that raises undoes all of it:

#. it locks the instance, reloads the object with ``select_for_update()`` and
   checks the permission and the condition again on that fresh copy. Two
   users racing for the same transition cannot both win: the second one is
   refused. Note that SQLite does not lock rows.
#. it applies the form, when that form is a ``ModelForm``, and saves it;
   ``Transition(..., variables=True)`` (or a list of field names) copies the
   form's data into the instance variables;
#. it sends ``pre_transition``;
#. it runs the ``on_exit`` actions of the state it leaves, the transition's
   actions and the ``on_enter`` actions of the activity it enters (the hooks
   only when the activity really changes);
#. it writes a ``FlowTransitionLog`` row: who, when, from where to where, the
   comment and the form data;
#. it sends ``post_transition``;
#. it does the work of the activity it entered -- a switch picks a branch, a
   human task creates its tasks -- and runs the automatic transitions the new
   state allows.

An action with ``on_commit = True``, such as ``CallFunction(f,
on_commit=True)`` or a custom one, runs only after the transaction commits.
Use it for anything a rollback cannot undo: an HTTP call, a queue, a file.

**Running as the system.** Code that is not a person -- seeding data, a data
migration, a command, a job -- runs a transition with
``flow.run(obj, 'publish', system=True)``, the way automatic transitions and
``Deadline`` timeouts run:

* no ``perms`` are checked;
* the source state and the ``condition`` are, with ``context.user`` set to
  ``None`` (a condition has to accept it);
* the ``FlowTransitionLog`` row has no user.

The flag is explicit on purpose. Without it, ``user=None`` or an anonymous
user is refused as any user without the permissions is, so a view that hands
over ``request.user`` -- or a missing one -- never runs as the system by
accident; and ``system=True`` takes no user (``ValueError``). ``flow.start(obj)``
checks no permission at all (there is no transition to check): without a user
it is a start by the system, and so are the automatic transitions it reaches.

**Who can reach what.** ``Flow.get_queryset(user)`` decides which objects a
user can see at all: the inbox, the detail page and the history. By default
it allows every object to users who have ``<app>.view_<model>``, and
otherwise only the objects they can act on or that are assigned to them or
to one of their groups. Override it to narrow it further::

    def get_queryset(self, user):
        return super().get_queryset(user).filter(owner=user)

Activities
----------

``states`` holds ``(value, label)`` tuples -- plain states -- and the
activities of ``djgentelella.flows.activities``. Everything but a state moves
on by itself.

.. code:: python

    from djgentelella.flows import (ActionActivity, HumanTask, Join, Parallel,
                                    SetField, Subflow, Switch, Wait)

    states = [
        ('draft', 'Draft'),
        Switch('route', cases=[('expenses.is_large', 'review')], default='manager'),
        HumanTask('manager', title='Approve {{ object }}', owners=['field:manager'],
                  outcomes={'approve': 'approved', 'reject': 'rejected'}),
        Parallel('review', branches=['manager_review', 'finance_review']),
        HumanTask('manager_review', owners=['field:manager'],
                  outcomes={'approve': 'reviewed', 'reject': 'reviewed'}),
        HumanTask('finance_review', groups=['Finance'],
                  outcomes={'approve': 'reviewed', 'reject': 'reviewed'}),
        Join('reviewed', wait_for='all', next='decide'),
        Switch('decide', cases=[('expenses.both_approved', 'approved')],
               default='rejected'),
        ActionActivity('approved', actions=[Notify('Approved', to='field:requester')],
                       next='payment'),
        Wait('payment', signal='paid', after=timedelta(days=30), next='paid'),
        ...
    ]

======================  =======================================================
``Switch``              goes to the target of the first case whose condition
                        holds, or to ``default``
``Wait``                until ``after`` (a duration or a callable returning a
                        date), until the date in the variable ``until``, or
                        until the signal ``signal`` -- whichever comes first --
                        then to ``next`` (required: a ``Wait`` without it is
                        ``ImproperlyConfigured``)
``Parallel``            one token per activity in ``branches``
``Join``                where the branches meet: on to ``next`` once
                        ``wait_for`` of them arrived (``'all'`` or a number);
                        the branches still under way are cancelled
``Subflow``             starts flow ``flow`` (on the same object, or on
                        ``obj``) with ``variables``, and waits until it
                        completes; then ``outcomes[<its final state>]`` or
                        ``next``. Its variables are copied into
                        ``variables[<activity id>]``
``HumanTask``           creates a task (below) and waits for its outcome;
                        ``outcomes`` maps each outcome to the next activity
``ActionActivity``      runs ``actions``, then ``next``
======================  =======================================================

While branches run in parallel, ``FlowInstance.state`` is the parallel
activity and ``flow.active_states(instance)`` lists the branches; the
transitions of each branch are offered as usual.

**Signals.** ``flow.signal(obj, 'paid', {'ref': 'X1'})`` wakes the waits of
the object that wait for ``paid`` and merges the data into the variables; it
returns how many woke up.

**Errors.** When an automatic activity raises -- an action that fails, a
switch that no case matches -- its work is undone and its token is left in
error, and so is the instance (``status='error'``, ``error`` says what failed;
the log has an ``error`` row). Nothing else is lost: the transition that led
there stays done. ``flow.retry(obj)`` enters the failed activities again.

**Limits.** The activities that move by themselves run one after the other in
a loop of the engine, not nested in each other, so a long chain of them needs
no Python stack. One run makes at most ``Run.MAX_STEPS`` (500) moves; more is
taken for a loop of automatic activities and the whole run is undone with
``ImproperlyConfigured``. Subflows nest at most ``GT_FLOWS_MAX_SUBFLOW_DEPTH``
deep (10 by default): the ``Subflow`` that would start one more is left in
error (flows that start each other on new objects stop there).

Variables
---------

``FlowInstance.variables`` is a JSON dict. A flow's ``variables`` attribute is
what a new instance starts with; ``flow.start(obj, user, variables={...})``
adds to it. Conditions read them, actions write them
(``SetVariable('total', 10)``, or ``context.variables[...] = ...`` in a
custom action), transition forms copy into them (``variables=True``), a human
task stores its outcome in ``variables['<activity>_outcome']`` and the data it
was completed with, a signal its data. ``flow.update_variables(obj, {...})``
changes them from outside, logged.

**Types of variable.** Tools that let people declare variables (a flow
designer) share one list of types, in ``djgentelella.flows.variables``:
``string``, ``integer``, ``decimal``, ``boolean``, ``date``, ``datetime``,
``user``, ``list`` and ``object``, each with a translatable label. Each says
which JSON values it takes
(``check_variable('integer', 3)``; ``True`` is only a ``boolean``), and a
project adds its own:

.. code:: python

    from djgentelella.flows import register_variable_type

    register_variable_type('money', (int, float, str),
                           json_types=('number', 'string'), label='Money')

``variable_types()`` lists them as JSON (see "What the engine registered").

Controlling an instance
-----------------------

* ``flow.suspend(obj, user)``: nothing moves it -- no transition, timer,
  signal nor task completion -- until ``flow.resume(obj, user)``;
* ``flow.terminate(obj, user)``: it ends where it is; its open tasks are
  cancelled and its subflows terminated;
* ``flow.retry(obj, user)``: enters again the activities that failed.

Each one is logged. They need ``Flow.control_perms`` (by default
``gtflows.change_flowinstance``); the detail page has their buttons.

Human tasks
-----------

A ``Task`` is a piece of work for a person. It has potential owners (users)
and groups, an actual owner, a state -- ``unassigned``, ``assigned``,
``info_requested``, ``completed``, ``cancelled``, ``expired`` --, a priority
from 1 (urgent) to 5, a due date, the outcomes it may end with, comments and
history. It belongs to a flow instance (a ``human_task`` waits for it), or
stands alone:

.. code:: python

    from djgentelella.flows import create_task

    task = create_task(obj=invoice, title='Check the invoice',
                       potential_owners=[ana], groups=['Accounting'],
                       due=timedelta(days=2), priority=2,
                       outcome_choices=('approve', 'reject'))
    task.claim(ana)                         # only a potential owner can
    task.request_info(ana, beto, 'Is the VAT right?')
    task.submit_info(beto, 'Yes')
    task.delegate(ana, carla)
    task.complete(carla, 'approve', comment='Fine', data={'checked': True})
    Task.objects.inbox(user)                # what the user can see or take

Each change locks the task's row and checks again who may do it, so two users
cannot both claim or complete one task. A potential owner may complete an
unclaimed task directly. ``task_created`` and ``task_completed`` are sent.

``HumanTask(...)`` takes ``title`` and ``description`` (templates),
``owners`` (recipients: ``'field:manager'``, ``'user:ana'``,
``'variable:approver'``, a callable...), ``groups``, ``priority``, ``due``
and ``on_expire``.

**Several approvers.** ``HumanTask(..., each=True, min=2)`` gives every person
(the owners and the members of the groups) a task of their own. The activity
is decided as soon as ``min`` of them -- a number, ``'all'`` or
``'majority'`` -- gave the same outcome, in the order of ``outcomes``; once no
outcome can reach ``min`` any more, the last outcome wins (a veto). The tasks
still open are cancelled. This replaces the ``Approval`` quorum and the
``FlowVote`` model of the first version.

**Due dates.** Past its ``due``, the timer processor applies ``on_expire``:

* ``{'outcome': 'reject'}`` completes it with that outcome, as the system;
* ``{'escalate': {'owners': [...], 'groups': [...], 'priority': 1, 'due':
  timedelta(days=1)}}`` hands it to them, unclaimed;
* ``{'notify': '{{ task }} is late'}`` notifies the owners (the new ones, when
  escalated).

Without any of them the task becomes ``expired``; a ``human_task`` with an
``expired`` outcome follows it.

**A form to fill in.** ``HumanTask(..., form=ReviewForm)``, or
``"form": "<name>"`` in JSON, gives the task a form: the task page shows it
above the outcome buttons (its fields start with the instance variables of
the same name), validates it -- an invalid form answers 400 with the errors
and the task stays open -- and its ``cleaned_data`` is the data the task is
completed with, so it is merged into the variables. A JSON flow names a form
registered with ``register_task_form``, or the dotted path of a form class
that the allowlist of JSON flows permits (``GT_FLOWS_ALLOWED_CALLABLES`` or
``register_callable``, see "Callables a JSON flow may name" below). Nothing
else is found, so a published flow cannot make the engine import an arbitrary
path: ``publish_definition`` refuses any other name (``$.states[i].form``,
from ``djgentelella.flows.taskforms.validate_task_forms``), and a document
stored some other way still loads but its ``human_task`` refuses to create
the task -- the activity is left in error, logged -- until the name is
allowed. ``get_task_form(name)`` is the one place a name becomes a class:

.. code:: python

    from djgentelella.flows import register_task_form

    @register_task_form('expenses.review')     # bare @register_task_form: its dotted path
    class ReviewForm(GTForm, forms.Form):
        amount = forms.DecimalField(max_digits=10, decimal_places=2)
        note = forms.CharField(required=False)

The values pass through JSON (a ``Decimal`` becomes text, a date ISO 8601);
the page does not send files. Code that completes a task itself passes the
data: ``task.complete(user, 'approve', data={...})``.

**When the object goes away.** Deleting an object cancels the open tasks of
every flow instance it had -- each with a ``cancel`` entry in its history --,
keeps all its tasks as tasks of no flow, and deletes the instances (their log
and their subflows go with them). That works for JSON flows too, even in a
process that never built the flow: when a process opens its first database
connection (and then at most once a minute) it watches every model a
``FlowDefinition`` runs on, and publishing a definition watches its model at
once. A task whose object is gone anyway (deleted with ``QuerySet.update``,
raw SQL, another database) is cancelled when someone tries to complete it --
they get "the object of this task no longer exists", never an error page --
or when it falls due. ``forget_object(Model, pk)`` does that cleanup by hand.
"Gone" means the row is not in the model's ``_base_manager``: an object that
a default manager hides (soft delete, archived, by Site) still exists, so its
instance and log are never forgotten; the engine still refuses to run on it
while it is hidden.

Timers
------

::

    deadlines = {
        'review': Deadline(timedelta(days=3), transition='escalate',
                           actions=[Notify('{{ object }} is late.', to='assigned')]),
    }

Entering ``review`` sets its deadline. ``after`` may also be a callable
``(context) -> datetime``. Once it passes, the deadline runs its ``actions``
and then its ``transition`` as the system, logged with kind ``timeout``.
Without a transition, the actions run once. A ``State`` can also carry its
own ``deadline=``.

``process_flow_timers`` runs everything due: deadlines, waits and the tasks
past due. ``FlowInstance.due_at`` is the earliest timer of an instance. Run it
from cron::

    python manage.py process_flow_timers            # --dry-run lists what is due

or call ``djgentelella.flows.timers.process_due()`` from your scheduler
(Django Tasks, Celery); with Celery, ``djgentelella.flows.tasks
.process_flow_timers_task`` is ready for beat.

Automatic transitions
---------------------

``Transition(..., auto=True)`` is never a button. Right after an object enters
one of its source states, the engine runs the first automatic transition, in
declaration order, whose ``condition`` holds (one without a condition always
does). They chain up to ``Flow.max_auto_steps`` (10); more than that is taken
for a loop and the whole run is undone with ``ImproperlyConfigured``. When the
object changes outside the flow, ``flow.evaluate(obj)`` runs the automatic
transitions its current state allows. A ``Switch`` does the same job as an
activity of its own.

Actions
-------

Every action has a registry ``name`` and a ``props_schema`` (JSON Schema), so
it can be declared as JSON -- ``{"action": "send_email", "props": {...}}`` --
by flow definitions and by automations that run actions outside any flow
(``flow=None``, ``instance=None``):

.. code:: python

    from djgentelella.flows import (Action, ActionContext, action_from_json,
                                    register_action)

    action_from_json({'action': 'notify', 'props': {'message': 'Hi', 'to': 'actor'}}
                     ).run(ActionContext(obj=obj, user=user))

    @register_action
    class Archive(Action):
        name = 'archive'
        props_schema = {'type': 'object', 'properties': {'reason': {'type': 'string'}}}

        def __init__(self, reason=''):
            self.reason = reason

        def run(self, context):
            ...

====================================  ==========================================
``SetField(field, value)``            ``set_field``: ``obj.field = value`` (a
                                      callable gets the context; ``variable=``
                                      takes it from the variables)
``SetVariable(name, value)``          ``set_variable``: instance variables
``Assign(user, group)``               ``assign``: a recipient or ``None``; a
                                      group name
``Notify(message, to)``               ``notify``: in-app notification
                                      (:doc:`notifications`); the message is a
                                      template with ``object``, ``user``,
                                      ``data``, ``variables``, ``flow``...
``SendEmail(code, to)``               ``send_email``: an async_notification
                                      ``EmailTemplate``
``CallFunction(f)``                   ``call``: ``f(context)``; ``f`` may be a
                                      dotted path
``CreateTask(title, owners, ...)``    ``create_task``: a task nothing waits for
``StartFlow(flow, obj, variables)``   ``start_flow``: starts another flow on
                                      its own
====================================  ==========================================

Recipients can be ``'actor'``, ``'assigned'``, ``'field:<path>'``,
``'variable:<name>'``, ``'user:<username>'``, ``'group:<name>'``, a callable,
and for emails an address or ``name@group.local``.

Action policy
~~~~~~~~~~~~~

Before each action runs (``run_actions``, which the engine and the
automations use), the **action policy** is asked: ``GT_FLOWS_ACTION_POLICY``
(a callable ``(action, context) -> bool``, an object with that ``allowed``
method, or the dotted path of either) and the context's own
``ActionContext(..., policy=...)``. Every one of them has to allow it. A
refusal -- or a policy that raises -- is logged as a warning, sends
``action_blocked`` (``action``, ``context``, ``reason``) and raises
``ActionNotAllowed``, a ``TransitionNotAllowed``: a transition is refused
and undone, an activity is left in error. Without a policy everything runs.
The reason the user may see is generic ("The action ... is not allowed
here."), and the error of a policy that raises goes only to the log; a policy
that wants to explain itself raises ``ActionNotAllowed('...')``, whose message
is kept as the reason.

.. code:: python

    class UntrustedPolicy:
        def allowed(self, action, context):
            return action.name in ('notify', 'set_variable')

    run_actions(actions, ActionContext(obj=row, user=run_as,
                                       policy=UntrustedPolicy()))

The texts of the actions (``notify`` messages, task titles, ``set_variable``
templates, the context of ``send_email``) are rendered with
``context.render_context()``: by default ``context.template_context``
(``object``, ``user``, ``flow``, ``transition``, ``activity``, ``data``,
``variables``, ``instance``, ``task``). ``ActionContext(...,
render_context=fn)`` replaces it with ``fn(context)``, so a caller that runs
actions for someone it does not trust reduces what their templates can
reach. A subclass may also override ``render_context()``.

Flows in JSON
-------------

A flow can also be a JSON document, validated by
``djgentelella/flows/schema_v2.json`` and stored in a ``FlowDefinition(name,
version, site, document, is_active)``. It builds the same ``Flow`` object a
class does, so the pages, the inbox and the diagram do not tell them apart.
Conditions are named (registered functions), actions are
``{"action", "props"}``, transition forms are dotted paths, ``human_task``
forms registered names, durations are seconds or ISO 8601 (``"P2D"``):

.. code:: json

    {
      "schema_version": 2, "name": "expenses.approval", "model": "expenses.Expense",
      "initial": "draft", "final_states": ["approved", "rejected"],
      "states": [
        {"id": "draft", "label": "Draft"},
        {"id": "route", "type": "switch",
         "cases": [{"condition": "expenses.is_large", "target": "finance"}],
         "default": "manager"},
        {"id": "manager", "type": "human_task", "owners": ["field:manager"],
         "outcomes": {"approve": "approved", "reject": "rejected"}},
        {"id": "finance", "type": "human_task", "groups": ["Finance"], "due": "P3D",
         "on_expire": {"outcome": "reject"},
         "outcomes": {"approve": "approved", "reject": "rejected"}},
        {"id": "approved"}, {"id": "rejected"}
      ],
      "transitions": [{"name": "submit", "source": "draft", "target": "route",
                       "perms": ["expenses.change_expense"]}]
    }

Publish it without restarting anything::

    python manage.py gtflows_publish approval.json [--site example.com] [--inactive]

or ``publish_definition(document, site=None)``. Each publication is a new
version, and the older versions of that name and site stop starting
instances. ``get_flow(name, site=site)`` returns the active definition with
the highest version -- the site's own before the global one -- and falls back
to the Python class of that name.

**A definition as data.** ``export_definition(definition)`` gives
``{'name', 'document'}`` (the document with its ``version``; no pk, no Site)
and ``export_definitions(site=None)`` the active version of each flow of a
Site, by name. ``import_definition(data, site=None)`` publishes it there: when
the active version already has the same document (``version`` aside) it is
returned as it is, otherwise the document becomes the next version. It checks
everything first (``validate_definition_data``: the shape, the name of the
document and what ``publish_definition`` checks) and raises
``ImproperlyConfigured`` without saving when something is wrong.

**Versions.** An instance stays bound to the version it started with
(``FlowInstance.version`` and ``definition``): publishing a new one does not
change the instances under way, and ``get_flow(name).run(obj, ...)`` runs the
object's own version. Python classes are versioned the same way: register a
class with ``version = 2`` under the same ``name`` and keep the old one
registered while it has instances.

**Callables a JSON flow may name.** A ``FlowDefinition`` is data, so the
dotted paths in it -- a condition (``"pkg.fn"`` or ``{"function": "pkg.fn"}``),
the ``function`` of a ``call`` action, the ``form`` of a transition or of a
``human_task`` -- must be allowed:

- registered with ``register_callable`` (functions and form classes) or, for
  conditions, with ``register_condition``, or, for the form of a
  ``human_task``, with ``register_task_form`` (by its registered name);
- or listed in ``GT_FLOWS_ALLOWED_CALLABLES``, a list of exact paths or
  prefixes: ``'myapp.flows'`` allows ``myapp.flows`` and everything under it.
  It is empty by default.

.. code:: python

    from djgentelella.flows import register_callable

    @register_callable
    def notify_erp(context):
        ...

``publish_definition`` (and ``gtflows_publish``) refuses a document that names
any other path, with the JSON path of each one: ``validate_callables(document)``
and ``validate_task_forms(document)`` return those errors, and
``validate_actions(specs, where='')`` those of a list of actions on its own
(an automation's, say), all three exported by ``djgentelella.flows``. Each
error is a ``(path, message)`` tuple, the ``Error`` of the design documents
(``DocumentError``, whose ``str()`` is ``'path: message'``). Read
``error.path`` and ``error.message``: an error is a tuple, not its text, so it
is not equal to ``'path: message'`` and has no ``str`` methods (until 0.8 it
answered them, a transitional bridge for code written when these validators
returned text). ``is_task_form_allowed(name)`` says whether a ``human_task`` may name a form. A document stored
some other way still loads, and the path is refused when it runs, logged on
``djgentelella.flows``: a condition or a form not allowed blocks its
transition (``TransitionBlocked``, shown as the reason), and a ``call`` raises
``CallableNotAllowed`` -- the transition is refused and rolled back, an
activity is left in error with the reason in its log. The check lives in
``action_from_json`` itself, so any action built from JSON -- by a flow, an
automation or a project's own code -- gets it. Flows declared as Python
classes are code, not data, and are not restricted (``CallFunction('pkg.fn')``
written in Python imports its path as is). The registered
authorization conditions (``{"perm": ...}`` and the rest) are not callables and need nothing.

The same criterion -- restrict the paths that come from data, trust the ones
that come from settings -- leaves two other ``import_string`` calls as they
are: ``GT_DESIGN_COMPONENTS`` (the extra design components,
``djgentelella.designs.registry``) and ``GT_SITE_GROUPS_RESOLVER``
(``djgentelella.authorization``) are read from the project settings, which only
whoever deploys the project writes, so they need no allowlist. Automations
that build actions from JSON with ``action_from_json`` directly do not go
through ``build_flow``; they opt in with
``djgentelella.flows.callables.guard_action(action, where)`` or
``validate_actions(specs)``.

Inboxes and pages
-----------------

djgentelella adds these URLs. All of them require login:

* ``task_inbox`` ``flows/inbox/`` lists the tasks of the user and of their
  groups, of every flow, with filters by flow, priority, state and due date
  (``?flow=``, ``?priority=``, ``?state=open|all|<state>``,
  ``?due=overdue|today|week|none``). With ``gtflows.view_task``, all of them.
* ``task_detail`` ``flows/tasks/<pk>/`` shows the task, its comments and
  history, and the forms to claim, release, delegate, request or submit
  information, comment and complete it (``task_action``
  ``flows/tasks/<pk>/<action>/``, POST).
* ``flow_inbox`` ``flows/<flow>/inbox/`` lists the objects waiting for the
  user in one flow: in a state from which the user holds the permissions of
  some transition, or assigned to the user or to one of their groups.
* ``flow_detail`` ``flows/<flow>/object/<pk>/`` shows the state and status,
  the transitions, the tasks, the variables, the control buttons, the
  history and the instance's diagram. 404 for an object the user cannot
  reach.
* ``flow_transition`` ``flows/<flow>/run/<transition>/<pk>/`` shows the form
  and a comment box, then runs the transition. It honours a ``?next=`` on the
  same host.
* ``flow_assign`` ``flows/<flow>/assign/<claim|release|reassign>/<pk>/``.
* ``flow_control`` ``flows/<flow>/control/<suspend|resume|terminate|retry>/<pk>/``
  (POST).
* ``flow_bulk`` ``flows/<flow>/bulk/`` takes the inbox's selection (POST).
* ``flow_diagram`` ``flows/<flow>/diagram/``.

With :doc:`datasources` installed, the task inbox is also the data source
``flows.tasks`` (``djgentelella/flows/gtdatasources.py``): the same tasks
``flows/inbox/`` lists (all of them with ``gtflows.view_task``), for any
authenticated user, with the columns ``id``, ``title``, ``state``,
``priority``, ``due``, ``instance__flow``, ``actual_owner``, ``outcome``,
``created_at`` and ``completed_at``. Its facets, saved parameters and exports
work as for any other source, under ``gtapis/datasources/flows.tasks/``.

Primary keys of any type are supported: UUIDs are stored as 32 hex digits,
everything else as text up to 255 characters. Deleting an object deletes its
flow state and cancels its open tasks (see `Human tasks`_).

Template tags, in ``{% load gtflows %}``:

.. code:: html+django

    {% flow_status object 'news.ArticleReviewFlow' %}
    {% flow_states articles 'news.ArticleReviewFlow' as states %}
    {% for article in articles %}{{ states|flow_label:article.pk }}{% endfor %}
    {% flow_diagram 'news.ArticleReviewFlow' object %}
    {% task_inbox_count %}

Claiming and reassigning objects
--------------------------------

An object assigned to a group can be **claimed** by one of its members and
**released** back: ``flow.claim(obj, user)``, ``flow.release(obj, user)``.
``flow.reassign(obj, user, to_user=..., to_group=...)`` needs
``Flow.reassign_perms`` (by default ``gtflows.change_flowinstance``). None of
them change the state. For work that needs an outcome, use human tasks.

Many objects at once
--------------------

``flow.run_many(objects, 'close', user)`` runs a transition on each object,
each in its own transaction, and returns ``.done`` and ``.refused``
(``[(obj, reason)]``). The flow inbox offers it with checkboxes for
transitions without a form, or with ``bulk=True``.

Kanban board
------------

The design component ``flow_kanban`` (:doc:`designs`, "Flow kanban") shows
the objects of a flow as cards in one column per state, from
``get_queryset(user)`` and the current Site. Dragging a card to another
column, or picking the column in its "Move to" menu, asks which transitions
go from one state to the other for that object and user (``Flow.check``) and
runs the chosen one with ``Flow.run``, its form in a modal: the same rules,
the same log, as the flow's own pages.

Diagram
-------

``flow.as_graph()`` is the flow as JSON nodes (with their ``type``) and edges:
``'*'`` is expanded, and automatic edges, timeouts and the routes of every
activity (cases, branches, outcomes) are included. djgentelella draws it as
an SVG on the server, without JavaScript. With an instance --
``flow.runtime(instance)``, used by the detail page and by
``{% flow_diagram flow object %}`` -- the activities under way, done and
failed are coloured (``data-status="active|completed|error"`` on each node).

``flow.unreachable_states()`` lists the activities no edge of the graph
reaches from the initial one, and ``flow.dead_ends()`` the ones that are not
final and from which no final activity can be reached (an instance there
never finishes): checks for a flow designer or an advisor.

``flow.instance_diagram(obj, user)`` is the diagram of one instance, what the
detail page shows:

* the current activity (``data-status="active"``) and those already done;
* the transitions the instance took, from its ``FlowTransitionLog``
  (``class="gt-flow-edge taken"``; a loop on one state only with its own
  transition name, so a claim or a change of variables does not light it up);
  ``runtime()`` returns them as ``taken`` (``[source, target, name]``, oldest
  first) and the states visited as ``path``;
* the transitions ``user`` may run now (``available_transitions``: its
  permissions and the conditions; automatic ones never), drawn dashed in the
  primary colour with ``data-transition="<name>"`` on their edge;
* in words, for a screen reader: the SVG is ``role="img"`` with a
  ``<title>`` (the flow and its current state) and a ``<desc>`` (the way
  taken, what failed and what the user can run), and every node carries a
  ``<title>`` with its status.

In a template:

.. code:: html+django

    {% load gtflows %}
    {% flow_diagram object %}                          {# the flow of its instance #}
    {% flow_diagram object flow='news.ArticleReviewFlow' %}
    {% flow_diagram 'news.ArticleReviewFlow' object %}  {# as before #}
    {% flow_diagram 'news.ArticleReviewFlow' %}         {# the bare flow #}

``{% flow_diagram object %}`` finds the flow of the object's most recent
instance or, without one, the only flow over its model; it draws nothing when
there is none or more than one could be meant.

Signals
-------

All of them are sent inside the transaction of the change: a receiver that
raises undoes it.

* ``pre_transition`` / ``post_transition``: ``flow``, ``obj``, ``instance``,
  ``transition``, ``user``, ``source``, ``target``, ``kind``;
* ``flow_state_changed``: ``flow``, ``instance``, ``old``, ``new``;
* ``task_created`` / ``task_completed``: ``task``, ``user`` (and
  ``outcome``). The engine's own receiver, which moves the flow, runs first.
* ``action_blocked``: ``action``, ``context``, ``reason`` (sender: the action
  class), right before ``ActionNotAllowed`` is raised -- a receiver's writes
  to the database go with the transaction that is undone.

What the engine registered
--------------------------

Tools on top of the engine (a flow designer, an automation editor) read the
registries through ``djgentelella.flows``, never through a ``_registry``.
Every function returns plain JSON (lists and dicts of strings, numbers and
booleans), sorted by name:

``registered_actions()``
    ``[{"name", "class", "help", "props_schema", "on_commit"}]``.
``registered_conditions()``
    ``[{"name", "help"}]`` of the ``register_condition`` functions.
``registered_task_forms()``
    ``[{"name", "class", "fields": [{"name", "label", "required", "type"}]}]``.
``registered_flows(published=False, site=None)``
    ``[{"name", "title", "model", "source", "versions", "initial", "states",
    "transitions", "auto"}]``: the flows declared in Python, without touching
    the database; with ``published``, the active definitions too
    (``source="definition"``). ``transitions`` are names, and ``auto`` is
    ``{transition: bool}``: an automatic transition is one no user runs (a
    row link of :doc:`designs` cannot name it).
``variable_types()``
    ``[{"name", "label", "json_types"}]``: the types of flow variables.
``activity_arguments()``
    ``{"common": COMMON, "types": ARGUMENTS}``.
``catalogue(published=False, site=None)``
    All of them in one document, with ``schema_version``.
``COMMON``, ``ARGUMENTS``
    The keys every activity of a JSON flow takes, and those of each ``type``.

The log
-------

``FlowTransitionLog`` keeps every event of an instance: transitions (by hand,
``auto``, ``timeout``), the activities entered by the engine (``activity``),
signals, task outcomes, errors, variable changes, assignments and the control
actions (``suspend``, ``resume``, ``terminate``, ``retry``). ``TaskHistory``
does the same for each task.

Demos
-----

``demo/demoapp/gtflows.py`` declares one flow per kind of process, and
``/flowdemos/`` shows them with their diagrams and a page each to create
objects and move them:

* **Expense approval**: a switch by amount, the manager's task and, for a
  large amount, the manager and finance in parallel joined before a second
  switch, then a wait for the payment signal ("Mark as paid").
* **Expense approval (JSON)**: the same flow in
  ``demoapp/flowdemos/expense_flow.json``, published by ``createdemo`` as a
  ``FlowDefinition``.
* **Purchase requests**: an automatic gateway by amount, a committee where
  every member gets a task and two approvals decide, a reminder on expiry.
* **Help desk**: automatic triage into a group queue, claim and release, an SLA
  that depends on the priority, cancelling from any state, bulk close. Its
  tickets are also on a kanban board, ``/designs/tickets-board/`` ("Board" on
  ``/flowdemos/``).
* **Editorial review**: a ``ModelForm`` in a transition, reasons on disabled
  buttons, ``on_exit`` hooks, a loop back for changes.
* **Leave requests**: the approver is a field of the object, tacit approval
  on a deadline, an ``on_commit`` action that writes the demo calendar.
* **Country approval**: the minimal example.

``manage.py createdemo`` creates the users ``ana``, ``beto`` and ``carla``
(password ``demo``; carla is in Finance) and objects in several states. Sign
in as each of them to see the task inbox, the flow inboxes and the disabled
buttons change. As a superuser, "Expire every deadline now" on ``/flowdemos/``
runs the timers without waiting for cron.
