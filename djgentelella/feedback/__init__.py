"""User feedback: a button on every page that opens a short form -- an
error, an idea or a question -- and an inbox where reviewers answer it.

The button is drawn by ``{% gt_feedback_button %}`` (at the end of
``base.html``) when ``GT_FEEDBACK`` is ``True`` and the request's Site has not
turned it off with the setting ``feedback_enabled`` (``false``), and only for
a user who is logged in. What it sends is the text and its type; the page
(path, without the query string) and the browser only when the user leaves
those boxes ticked; never the values of the page's forms.

Reviewers need ``djgentelella.view_feedback`` to read the inbox and
``djgentelella.change_feedback`` to answer; they see the feedback of the
request's Site and the global one (:func:`djgentelella.sites.site_q`). An
answer notifies its author through the notification bell
(:func:`djgentelella.notification.create_notification`).
"""
