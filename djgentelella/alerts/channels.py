"""Channels: how a fired alert reaches people.

A channel gets every event of the processes that use it, with the users the
rule resolved: :meth:`AlertChannel.send` when the alert fires (and again when
it is repeated), :meth:`AlertChannel.on_resolve` when it is closed. Two come
registered:

- ``email``: :class:`EmailChannel`, an async_notification template
  (``rule.notification_code`` or the process's). Pass ``sender`` to route it
  through a function of your own.
- ``notification``: :class:`NotificationChannel`, the bell of
  ``djgentelella.notification``.

A project registers its own (a pending task, a chat message...) with
:func:`register_channel`, or replaces one of these under the same name.
"""

import logging

from django.utils.module_loading import import_string

from djgentelella.notification import create_notification

logger = logging.getLogger(__name__)

CHANNELS = {}

#: alert level -> Notification.message_type
LEVEL_MESSAGE_TYPE = {'info': 'info', 'medium': 'warning', 'critical': 'danger'}


class AlertChannel:
    """Base channel. ``name`` is how processes refer to it."""

    name = None

    def applies(self, event):
        """Whether this event goes through this channel at all."""
        return True

    def send(self, event, users, context):
        raise NotImplementedError

    def on_resolve(self, event, resolution=None, user=None):
        """The event was resolved; ``resolution`` is the evidence, if any."""


class EmailChannel(AlertChannel):
    """An email from an async_notification template.

    :param sender: ``callable(event, code, emails, context)`` that sends it
        instead of ``send_email_from_template``, e.g. to pick a template per
        organization.
    """

    name = 'email'
    default_sender = ('djgentelella.async_notification.sending.'
                      'send_email_from_template')

    def __init__(self, sender=None):
        self.sender = sender

    def get_code(self, event):
        return event.rule.get_notification_code()

    def send(self, event, users, context):
        code = self.get_code(event)
        emails = sorted({user.email for user in users if getattr(user, 'email', '')})
        if not code or not emails:
            return
        if self.sender is not None:
            self.sender(event, code, emails, context)
            return
        # By path: async_notification is optional, and importing its models
        # without the app installed is an error.
        send = import_string(self.default_sender)
        send(code, emails, context)


class NotificationChannel(AlertChannel):
    """A notification in the bell of each user.

    :param levels: the alert levels it notifies; ``None`` is all of them.
    """

    name = 'notification'

    def __init__(self, levels=None):
        self.levels = tuple(levels) if levels is not None else None

    def applies(self, event):
        return self.levels is None or event.level in self.levels

    def send(self, event, users, context):
        message_type = LEVEL_MESSAGE_TYPE.get(event.level, 'info')
        for user in users:
            create_notification(str(event.message), user, message_type,
                                link=event.link or '')


def register_channel(channel):
    """Register ``channel`` (an instance) under its ``name``, replacing any."""
    if not channel.name:
        raise ValueError('An alert channel needs a name.')
    CHANNELS[channel.name] = channel
    return channel


def unregister_channel(name):
    CHANNELS.pop(name, None)


def get_channels(names=None):
    """The registered channels, or those of ``names`` that exist."""
    if names is None:
        return list(CHANNELS.values())
    return [CHANNELS[name] for name in names if name in CHANNELS]


register_channel(EmailChannel())
register_channel(NotificationChannel())
