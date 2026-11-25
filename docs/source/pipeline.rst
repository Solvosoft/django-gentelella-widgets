Page pipeline
=============

A design page (:doc:`designs`) can declare what happens before it is drawn and
when one of its forms is sent -- validate, compute fields, run processes and
decide where to go -- without a view written by hand. The steps are Python
functions the project registers by name, the way it registers conditions
(:doc:`authorization`), flow actions or components.

The module is ``djgentelella.designs.pipeline``.

Steps
-----

A step is a function ``fn(ctx, **params)`` registered with a name of the form
``app.name`` and one of three kinds:

``validation``
    Adds errors with ``ctx.add_error(field, message)`` (``field=None`` for the
    whole form) or raises ``ValidationError`` (a ``dict`` per field, a message
    for the form). Every validation runs; with one error the submission stops:
    nothing is computed or saved.
``computation``
    Sets values before the save with ``ctx.set_value(field, value)`` or by
    returning ``{field: value}``. Only fields of the form, or the ones the step
    declares in ``writes`` in the document, and never the primary key nor the
    version of optimistic locking (``GTLockMeta.version_field``,
    :doc:`locking`): doing otherwise is a bug of the step -- logged, nothing
    saved.
``process``
    Runs inside the transaction of the save, after it: ``ctx.instance`` is
    the saved object. Any error rolls the save and every process back. A
    ``ValidationError`` shows its messages; any other exception is logged and
    the form says the step could not be completed and nothing was saved.

::

    # shop/gtdesigns.py -- imported when the project starts
    from django.core.exceptions import ValidationError
    from django.db.models import F

    from djgentelella.designs.pipeline import process, register_process


    @process('shop.check_stock', kind='validation', label='Check the stock')
    def check_stock(ctx):
        item, quantity = ctx.data.get('item'), ctx.data.get('quantity')
        if item and quantity and quantity > item.stock:
            ctx.add_error('quantity', 'Only %d in stock' % item.stock)


    @process('shop.order_total', kind='computation')
    def order_total(ctx):
        return {'total': ctx.data['item'].price * ctx.data['quantity']}


    @process('shop.take_stock', kind='process')
    def take_stock(ctx):
        order = ctx.instance
        if not Item.objects.filter(pk=order.item_id, stock__gte=order.quantity) \
                .update(stock=F('stock') - order.quantity):
            raise ValidationError('The stock ran out', code='no_stock')


    register_process('shop.notify', notify, kind='process',
                     schema={'type': 'object', 'required': ['group'],
                             'additionalProperties': False,
                             'properties': {'group': {'type': 'string'}}})

``schema`` is the JSON Schema of the step's ``params``
(:mod:`djgentelella.designs.jsonschema`); without one the step takes none.
Registering a name again replaces the step. ``registered_processes(kind=None)``
and ``catalogue()`` list them (``catalogue()`` as data, for an editor);
``unregister_process(name)`` removes one.

The context
~~~~~~~~~~~

``ctx`` is a ``PipelineContext``:

====================  ==========================================================
``request``           the request; ``site`` and ``user`` come from it
``page``, ``node``    the ``Page`` and the id of the component
``event``             ``'before_render'`` or ``'on_submit'``
``form``              the form (crud_classic) or serializer (object_management)
``data``              its cleaned data, with what the computations set
``instance``          the object edited or, after the save, the one created
``parent``            the object of a page about one (``meta.parent``)
``values``            what the computations set
``step``              the ``StepBuild`` running (its ``name``, ``params``...)
====================  ==========================================================

and the methods ``add_error``, ``set_value``, ``add_context(**values)``
(``before_render``) and ``redirect(url)`` (a local URL, instead of the
branches).

The document
------------

A component with a form -- ``object_management``,
``inline_object_management`` and ``crud_classic`` -- takes
``props.pipeline.on_submit``; the page (the root node) takes
``props.pipeline.before_render``::

    "pipeline": {"on_submit": {
        "steps": [
            {"name": "shop.check_stock"},
            {"name": "shop.order_total", "writes": ["total"]},
            {"name": "shop.take_stock",
             "condition": {"perm": "shop.add_order"}},
            {"name": "shop.notify", "params": {"group": "sales"}}],
        "branches": [
            {"to": "page:orders/review", "condition": {"auth": "big_order"}},
            {"to": "page:orders/done"}]}}

Each step has its ``name``, its ``params`` and an optional ``condition``
(:doc:`authorization`; on a form it is evaluated with the object being saved,
before the page with the object of a page about one). The steps run by kind --
validations, computations, processes -- whatever their order in the list, and
in the list's order within a kind.

``branches`` are tried in order after the save; the first whose condition
holds (evaluated with the saved object) is where the request goes. One without
a condition is the default and must be the last. A target is:

- ``page:<path>``: a published design page; one about the model of the form
  (``meta.parent``) gets the saved object's pk;
- ``flow:<name>[:<transition>]``: the page of a flow (or of one transition) of
  the saved object, as the row links (:doc:`flows`); the transition checks its
  own permissions there;
- a URL name of the project, without arguments or taking the saved pk;
- a local path (``/...``).

Without branches the component does what it did before: the classic CRUD goes
back to its list, a table closes its modal. With one, the classic CRUD
redirects and the table's API answers ``gtdesign_redirect``, which the page
follows.

What happens on each component
------------------------------

``crud_classic``
    The create and update pages: errors show on the form (an error of a
    field the form does not have becomes a general one) and nothing is saved.
    The save, ``form_valid``, and the processes share one transaction.
``object_management`` and ``inline_object_management``
    ``create`` and ``update`` of the API (``perform_create``/
    ``perform_update``): the errors are a 400 with the fields' errors and the
    general ones in ``detail``; the success response carries
    ``gtdesign_redirect`` when a branch is taken. With ``optimistic_lock`` the
    order stays conditions (403), version (409), validation (400): the pipeline
    runs after the version check. A column hidden by its condition cannot be
    set on an update.
The page (``before_render``)
    Runs before each request draws the page, after its permissions: a
    validation error or a failing process refuses the page (403), a branch or
    ``ctx.redirect()`` redirects (the login page of an application, another
    branch), and ``add_context`` plus the computed values reach the template as
    ``pipeline`` (also the ``html`` nodes in template mode).

Elsewhere: ``run_pipeline``
---------------------------

The same for anything else that sends a form (a wizard, a view of the
project)::

    from djgentelella.designs.pipeline import (
        context_for_form, form_errors_to, run_pipeline,
    )

    ctx = context_for_form(form, request, node='order')
    result = run_pipeline(build.pipeline, ctx,
                          save=lambda ctx: form.save())
    if not result.ok:
        form_errors_to(form, result)          # or serializer_errors(result)
        return self.form_invalid(form)
    return redirect(result.url or default_url)

``run_pipeline(pipeline, ctx, *, save=None, using=None)`` returns a
``PipelineResult`` with ``ok``, ``errors`` (``[(field or None, message)]``),
``url``, ``values``, ``context``, ``saved`` and ``failed``. ``pipeline`` is a
``PipelineBuild`` -- what ``resolve_pipeline(rctx, props, path, event=...,
model=..., exposure=..., form_fields=...)`` makes of a document -- or ``None``
(only the save). ``save(ctx)`` returns the saved object.

In code, ``build_pipeline(stage, *, model=None, event='on_submit',
form_fields=None, site=None, intermediate=False)`` makes the
``PipelineBuild`` of a stage (``{"steps": [...], "branches": [...]}``) with
the same checks, raising ``ImproperlyConfigured`` with every problem.
``intermediate=True`` (also in ``resolve_pipeline``) is a stage that saves
nothing -- a step of a wizard --: a process or a branch is an error. The
wizard runs both kinds: see :doc:`wizard`.

Validation when publishing
--------------------------

Everything that can be checked without a request is an error of the document,
reported by ``validate``/``publish`` (``gtdesigns_publish``, the admin):

- a step that is not registered (asked through the hook
  ``ResolveContext.pipeline_step(name, path)``, which an editor can answer
  with steps it generates);
- ``params`` that do not fit the step's schema, an invalid condition;
- ``writes`` on a step that is not a computation, or naming a field the
  exposure of the model does not allow, the primary key, a field that is not
  editable or the version of optimistic locking;
- a default branch that is not the last, a target that does not exist, a
  ``flow:`` or a page about one object where there is no saved object;
- a ``before_render`` branch that leads back to its own page, directly or
  through the ``before_render`` of the published pages it goes to.

Security and audit
------------------

- The document names steps only by their registered name: it never imports a
  path.
- Steps run as the user of the request, after the permissions and conditions of
  the component (a user who cannot create gets a 403 and no step runs). There
  is no way for a step to act as the system: a branch to a flow opens its page,
  where ``Flow.run`` checks the transition.
- A failing process is logged on ``djgentelella.designs.pipeline``: the step,
  the moment, the page, the node, the user's pk and where it failed
  (exception class and traceback frames), never its message nor the data of
  the form. A process that refuses with ``ValidationError`` is logged as a
  warning with its error codes.

Demo
----

``/designs/shop-orders/`` (``demo/demoapp/gtdesign/shop_orders.json``): a
classic CRUD of orders whose pipeline checks the stock
(``demoapp.check_stock``), computes the total (``demoapp.order_total``, with
``writes: ["total"]``), takes the stock (``demoapp.take_stock``) and goes to
``/designs/shop-orders/done``. The steps are in ``demo/demoapp/gtdesigns.py``.
