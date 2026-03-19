from unittest.mock import patch, MagicMock, call

from django.core import mail
from django.contrib.auth.models import Group

from djgentelella.async_notification.tests import AsyncNotificationTestBase
from djgentelella.async_notification.models import (
    EmailNotification, EmailTemplate
)
from djgentelella.async_notification.sending import (
    resolve_all_recipients, chunk_list, do_send_notification,
    send_email_from_template,
)
from djgentelella.async_notification.resolvers import (
    RecipientResolverRegistry, DjangoGroupResolver
)


class ResolveAllRecipientsTest(AsyncNotificationTestBase):

    def test_empty_string(self):
        self.assertEqual(resolve_all_recipients(''), [])

    def test_none(self):
        self.assertEqual(resolve_all_recipients(None), [])

    def test_single_email(self):
        result = resolve_all_recipients('user@example.com')
        self.assertEqual(result, ['user@example.com'])

    def test_multiple_emails(self):
        result = resolve_all_recipients('a@b.com, c@d.com')
        self.assertEqual(result, ['a@b.com', 'c@d.com'])

    def test_deduplication(self):
        result = resolve_all_recipients('a@b.com, a@b.com, c@d.com')
        self.assertEqual(result, ['a@b.com', 'c@d.com'])

    def test_group_resolution(self):
        group = Group.objects.create(name='senders')
        self.user.groups.add(group)
        result = resolve_all_recipients('senders@group.local')
        self.assertIn(self.user.email, result)


class ChunkListTest(AsyncNotificationTestBase):

    def test_basic_chunking(self):
        result = chunk_list([1, 2, 3, 4, 5], 2)
        self.assertEqual(result, [[1, 2], [3, 4], [5]])

    def test_chunk_larger_than_list(self):
        result = chunk_list([1, 2], 10)
        self.assertEqual(result, [[1, 2]])

    def test_empty_list(self):
        result = chunk_list([], 5)
        self.assertEqual(result, [])

    def test_zero_size(self):
        result = chunk_list([1, 2, 3], 0)
        self.assertEqual(result, [[1, 2, 3]])


class DoSendNotificationTest(AsyncNotificationTestBase):

    def test_simple_send(self):
        notification = EmailNotification.objects.create(
            subject='Test Send',
            message='<p>Hello</p>',
            recipients='recipient@example.com',
        )
        do_send_notification(notification.pk)
        notification.refresh_from_db()
        self.assertEqual(notification.status, 'sent')
        self.assertTrue(notification.sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Test Send')
        self.assertEqual(mail.outbox[0].to, ['recipient@example.com'])

    def test_send_multiple_recipients(self):
        notification = EmailNotification.objects.create(
            subject='Multi',
            message='<p>Hi</p>',
            recipients='a@b.com, c@d.com',
        )
        do_send_notification(notification.pk)
        notification.refresh_from_db()
        self.assertEqual(notification.status, 'sent')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('a@b.com', mail.outbox[0].to)

    def test_send_individually(self):
        notification = EmailNotification.objects.create(
            subject='Individual',
            message='<p>Hi</p>',
            recipients='a@b.com, c@d.com',
            send_individually=True,
        )
        do_send_notification(notification.pk)
        notification.refresh_from_db()
        self.assertEqual(notification.status, 'sent')
        self.assertEqual(len(mail.outbox), 2)

    def test_send_with_bcc_cc(self):
        notification = EmailNotification.objects.create(
            subject='BCC/CC',
            message='<p>Hi</p>',
            recipients='main@example.com',
            bcc='bcc@example.com',
            cc='cc@example.com',
        )
        do_send_notification(notification.pk)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('bcc@example.com', mail.outbox[0].bcc)
        self.assertIn('cc@example.com', mail.outbox[0].cc)

    def test_no_recipients(self):
        notification = EmailNotification.objects.create(
            subject='Empty',
            message='<p>Hi</p>',
            recipients='',
        )
        do_send_notification(notification.pk)
        notification.refresh_from_db()
        self.assertEqual(notification.status, 'sent')
        self.assertEqual(len(mail.outbox), 0)

    def test_nonexistent_notification(self):
        # Should not raise
        do_send_notification(99999)

    def test_already_sent(self):
        notification = EmailNotification.objects.create(
            subject='Already Sent',
            message='<p>Hi</p>',
            recipients='a@b.com',
            status='sent',
        )
        do_send_notification(notification.pk)
        self.assertEqual(len(mail.outbox), 0)

    def test_resolved_recipients_stored(self):
        notification = EmailNotification.objects.create(
            subject='Test',
            message='<p>Hi</p>',
            recipients='a@b.com, c@d.com',
        )
        do_send_notification(notification.pk)
        notification.refresh_from_db()
        self.assertIn('a@b.com', notification.recipients_raw)
        self.assertIn('c@d.com', notification.recipients_raw)


class DoSendNotificationRetryTest(AsyncNotificationTestBase):

    def _make_notification(self, max_retries=2, **kwargs):
        return EmailNotification.objects.create(
            subject='Retry Test',
            message='<p>Hello</p>',
            recipients='recipient@example.com',
            max_retries=max_retries,
            **kwargs,
        )

    def _always_failing_connection(self, error_msg='SMTP connection refused'):
        conn = MagicMock()
        conn.send_messages.side_effect = Exception(error_msg)
        conn.__enter__ = lambda s: s
        conn.__exit__ = MagicMock(return_value=False)
        return conn

    def test_retries_until_max_then_fails(self):
        """Agota todos los reintentos y queda en status=failed."""
        notification = self._make_notification(max_retries=2)

        with patch('djgentelella.async_notification.sending.get_connection') as mock_conn:
            mock_conn.return_value.open.return_value = None
            mock_conn.return_value.send_messages.side_effect = Exception('SMTP down')

            do_send_notification(notification.pk)

        notification.refresh_from_db()
        self.assertEqual(notification.status, 'failed')
        # max_retries=2 → intentos 0,1,2 → retry_count debe ser 3
        self.assertEqual(notification.retry_count, 3)
        self.assertIn('SMTP down', notification.error_message)

    def test_succeeds_on_first_attempt(self):
        """Sin errores, queda en status=sent con retry_count=0."""
        notification = self._make_notification(max_retries=3)

        do_send_notification(notification.pk)

        notification.refresh_from_db()
        self.assertEqual(notification.status, 'sent')
        self.assertTrue(notification.sent)
        self.assertEqual(notification.retry_count, 0)

    def test_succeeds_on_second_attempt(self):
        """Falla una vez y luego envía exitosamente."""
        notification = self._make_notification(max_retries=2)
        call_count = {'n': 0}

        original_get_connection = __import__(
            'django.core.mail', fromlist=['get_connection']
        ).get_connection

        def flaky_connection(*args, **kwargs):
            call_count['n'] += 1
            if call_count['n'] == 1:
                conn = MagicMock()
                conn.open.side_effect = Exception('First attempt fails')
                return conn
            return original_get_connection(*args, **kwargs)

        with patch('djgentelella.async_notification.sending.get_connection', flaky_connection):
            do_send_notification(notification.pk)

        notification.refresh_from_db()
        self.assertEqual(notification.status, 'sent')
        self.assertTrue(notification.sent)
        self.assertEqual(notification.retry_count, 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_max_retries_zero_fails_immediately(self):
        """Con max_retries=0, un solo fallo marca como failed sin reintentar."""
        notification = self._make_notification(max_retries=0)

        with patch('djgentelella.async_notification.sending.get_connection') as mock_conn:
            mock_conn.return_value.open.side_effect = Exception('Instant fail')

            do_send_notification(notification.pk)

        notification.refresh_from_db()
        self.assertEqual(notification.status, 'failed')
        self.assertEqual(notification.retry_count, 1)

    def test_error_message_stored(self):
        """El mensaje de error del último intento queda guardado."""
        notification = self._make_notification(max_retries=1)

        with patch('djgentelella.async_notification.sending.get_connection') as mock_conn:
            mock_conn.return_value.open.side_effect = Exception('Timeout error XYZ')

            do_send_notification(notification.pk)

        notification.refresh_from_db()
        self.assertIn('Timeout error XYZ', notification.error_message)

    def test_already_sent_skips_retry(self):
        """Una notificación ya enviada no se vuelve a intentar."""
        notification = self._make_notification(max_retries=3, status='sent', sent=True)

        with patch('djgentelella.async_notification.sending.get_connection') as mock_conn:
            do_send_notification(notification.pk)
            mock_conn.assert_not_called()

        notification.refresh_from_db()
        self.assertEqual(notification.retry_count, 0)


class SendEmailFromTemplateTest(AsyncNotificationTestBase):

    def test_basic_template_send(self):
        EmailTemplate.objects.create(
            code='welcome',
            subject='Welcome {{ name }}',
            message='<p>Hello {{ name }}, welcome!</p>',
        )
        notification = send_email_from_template(
            code='welcome',
            recipient='new@user.com',
            context={'name': 'Alice'},
            enqueued=True,
        )
        self.assertEqual(notification.subject, 'Welcome Alice')
        self.assertIn('Hello Alice', notification.message)
        self.assertEqual(notification.recipients, 'new@user.com')
        self.assertTrue(notification.enqueued)

    def test_template_with_bcc_cc(self):
        EmailTemplate.objects.create(
            code='with-bcc',
            subject='Subject',
            message='Message',
            bcc='template-bcc@example.com',
            cc='template-cc@example.com',
        )
        notification = send_email_from_template(
            code='with-bcc',
            recipient='user@example.com',
            context={},
            bcc='extra-bcc@example.com',
            cc='extra-cc@example.com',
        )
        self.assertIn('template-bcc@example.com', notification.bcc)
        self.assertIn('extra-bcc@example.com', notification.bcc)
        self.assertIn('template-cc@example.com', notification.cc)
        self.assertIn('extra-cc@example.com', notification.cc)

    def test_template_not_found(self):
        with self.assertRaises(EmailTemplate.DoesNotExist):
            send_email_from_template(
                code='nonexistent',
                recipient='a@b.com',
                context={},
            )

    def test_immediate_send(self):
        from unittest.mock import patch
        from djgentelella.async_notification.backends.sync import SyncBackend
        EmailTemplate.objects.create(
            code='immediate',
            subject='Immediate',
            message='<p>Now</p>',
        )
        with patch('djgentelella.async_notification.backends.get_backend',
                   return_value=SyncBackend()):
            notification = send_email_from_template(
                code='immediate',
                recipient='now@user.com',
                context={},
                enqueued=False,
            )
        self.assertFalse(notification.enqueued)
