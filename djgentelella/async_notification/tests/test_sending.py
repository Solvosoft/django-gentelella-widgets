import base64
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import Group

from djgentelella.async_notification.tests import AsyncNotificationTestBase
from djgentelella.async_notification.models import (
    AttachedFile, EmailNotification, EmailTemplate
)
from djgentelella.async_notification import settings as ansettings
from djgentelella.async_notification.sending import (
    resolve_all_recipients, chunk_list, do_send_notification,
    build_email_message, rewrite_inline_images, send_email_from_template,
)
from djgentelella.async_notification.resolvers import (
    RecipientResolverRegistry, DjangoGroupResolver
)

# 1x1 transparent PNG
PNG_BYTES = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAE'
    'hQGAhKmMIQAAAABJRU5ErkJggg==')


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
        self.assertEqual(notification.recipients, ['new@user.com'])
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
        EmailTemplate.objects.create(
            code='immediate',
            subject='Immediate',
            message='<p>Now</p>',
        )
        notification = send_email_from_template(
            code='immediate',
            recipient='now@user.com',
            context={},
            enqueued=False,
        )
        self.assertFalse(notification.enqueued)


class InlineImageSendTest(AsyncNotificationTestBase):

    def test_rewrite_inline_images(self):
        html = '<p><img src="https://x/async_notification/preview-file/7/"></p>'
        self.assertIn('src="cid:img_7"', rewrite_inline_images(html))

    def test_cid_and_inline_attachment(self):
        notification = EmailNotification.objects.create(
            subject='Inline', message='placeholder',
            recipients=['dest@example.com'])
        att = AttachedFile.objects.create(
            content_type=ContentType.objects.get_for_model(EmailNotification),
            object_id=notification.pk,
            file=SimpleUploadedFile('img.png', PNG_BYTES,
                                    content_type='image/png'),
            is_inline=True,
        )
        notification.message = (
            f'<p><img src="/async_notification/preview-file/{att.pk}/"></p>')
        notification.save(update_fields=['message'])

        do_send_notification(notification.pk)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn(f'cid:img_{att.pk}', sent.body)
        cids = [p.get('Content-ID') for p in sent.message().walk()
                if p.get('Content-ID')]
        self.assertIn(f'img_{att.pk}', cids)

    def test_inline_image_unlinked_still_embeds(self):
        """An uploaded image (object_id=0, not reassociated) still embeds."""
        att = AttachedFile.objects.create(
            content_type=ContentType.objects.get_for_model(EmailNotification),
            object_id=0,
            file=SimpleUploadedFile('img.png', PNG_BYTES,
                                    content_type='image/png'),
            is_inline=True,
        )
        notification = EmailNotification.objects.create(
            subject='Inline', recipients=['dest@example.com'],
            message=(f'<p><img src="/async_notification/preview-file/'
                     f'{att.pk}/"></p>'))
        do_send_notification(notification.pk)
        sent = mail.outbox[0]
        self.assertIn(f'cid:img_{att.pk}', sent.body)
        cids = [p.get('Content-ID') for p in sent.message().walk()
                if p.get('Content-ID')]
        self.assertIn(f'img_{att.pk}', cids)


class BaseTemplateSendTest(AsyncNotificationTestBase):

    def setUp(self):
        self._orig = dict(ansettings.ASYNC_NOTIFICATION_BASE_TEMPLATES)
        ansettings.ASYNC_NOTIFICATION_BASE_TEMPLATES['default'] = (
            'async_notification/email_base.html')

    def tearDown(self):
        ansettings.ASYNC_NOTIFICATION_BASE_TEMPLATES.clear()
        ansettings.ASYNC_NOTIFICATION_BASE_TEMPLATES.update(self._orig)

    def test_base_template_wraps_body(self):
        notification = EmailNotification.objects.create(
            subject='Wrapped', message='<p>Hello</p>',
            recipients=['dest@example.com'], base_template='default')
        msg = build_email_message(notification, ['dest@example.com'])
        self.assertIn('async-email-body', msg.body)
        self.assertIn('Hello', msg.body)

    def test_send_from_template_sets_base_template(self):
        EmailTemplate.objects.create(
            code='wrapped', subject='S', message='<p>Hi</p>',
            base_template='default')
        notification = send_email_from_template(
            code='wrapped', recipient='u@x.com', context={})
        self.assertEqual(notification.base_template, 'default')


class RetryBackoffTest(AsyncNotificationTestBase):

    def _failing_send(self, notification):
        with patch('djgentelella.async_notification.sending.get_connection') \
                as gc:
            gc.return_value.open.side_effect = Exception('smtp down')
            do_send_notification(notification.pk)

    def test_failure_increments_and_stays_pending(self):
        notification = EmailNotification.objects.create(
            subject='S', message='M', recipients=['a@b.com'], max_retries=3)
        self._failing_send(notification)
        notification.refresh_from_db()
        self.assertEqual(notification.status, 'pending')
        self.assertEqual(notification.retry_count, 1)
        self.assertIsNotNone(notification.last_attempt)
        self.assertIn('smtp down', notification.error_message)
        self.assertEqual(len(mail.outbox), 0)

    def test_exhausted_retries_marked_failed(self):
        notification = EmailNotification.objects.create(
            subject='S', message='M', recipients=['a@b.com'], max_retries=1)
        self._failing_send(notification)
        notification.refresh_from_db()
        self.assertEqual(notification.status, 'failed')
        self.assertEqual(notification.retry_count, 1)
