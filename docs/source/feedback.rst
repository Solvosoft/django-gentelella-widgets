User feedback
=============

A button on every page of ``gentelella/base.html`` lets a signed-in user
leave a comment -- an error, an idea or a question -- and an inbox lets the
reviewers answer it.

Turning it on
-------------

.. code:: python

    GT_FEEDBACK = True

A Site turns it off with the database setting ``feedback_enabled``
(:doc:`sites`): ``false`` (or ``0``, ``no``, ``off``) for that Site; with the
global value ``false``, a Site turns it back on with ``true``. An anonymous
user never sees it. When it is off the button is not drawn and the endpoint
answers 404.

What is sent
------------

``{% gt_feedback_button %}`` (``{% load gtfeedback %}``, at the end of the
``footer`` block of ``base.html``) draws a tab on the right edge that opens a
modal: the type and the text, and two boxes, ticked by default, to add the
address of the page and the browser (user agent, screen and window size,
language). Only those: never the values of the page's forms. The server keeps
the path of the address without its query string (which may carry what a
search form typed) and only when it is a path of the same site, and the slug
of the design page when the page has one (``data-gtdesign-page``).

A ``djgentelella.models.Feedback`` keeps the user, the Site of the request,
the type, the text, the page, the design page, the browser, its status
(new, under review, answered, closed) and the answer, with who answered and
when.

Reviewing
---------

``gt_feedback_inbox`` (``/gt-feedback/``) lists the feedback of the
request's Site and the global one, newest first, filtered by status and type;
it needs ``djgentelella.view_feedback``. ``gt_feedback_detail``
(``/gt-feedback/<pk>/``) shows one: its author reads it with the answer; a
reviewer with ``djgentelella.change_feedback`` changes its status and answers
it. A new answer marks it answered (unless it was given another status) and
notifies its author with ``djgentelella.notification.create_notification``,
linking to the feedback. Anyone else gets a 404.
