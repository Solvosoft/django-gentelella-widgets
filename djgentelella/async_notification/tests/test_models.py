from django.db import IntegrityError
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from djgentelella.async_notification.tests import AsyncNotificationTestBase
from djgentelella.async_notification.models import (
    EmailTemplate, EmailNotification, AttachedFile,
    NewsLetterTemplate, NewsLetter, NewsLetterTask
)


class EmailTemplateModelTest(AsyncNotificationTestBase):

    def test_create_email_template(self):
        template = EmailTemplate.objects.create(
            code='welcome-email',
            subject='Welcome!',
            message='<p>Hello {{ user.name }}</p>'
        )
        self.assertEqual(template.code, 'welcome-email')
        self.assertEqual(template.subject, 'Welcome!')
        self.assertIsNotNone(template.created_at)
        self.assertIsNotNone(template.updated_at)

    def test_code_uniqueness(self):
        EmailTemplate.objects.create(
            code='unique-code', subject='Test', message='msg')
        with self.assertRaises(IntegrityError):
            EmailTemplate.objects.create(
                code='unique-code', subject='Test2', message='msg2')

    def test_str_representation(self):
        template = EmailTemplate.objects.create(
            code='test', subject='My Subject', message='body')
        self.assertEqual(str(template), 'test - My Subject')

    def test_defaults(self):
        template = EmailTemplate.objects.create(
            code='defaults', subject='S', message='M')
        self.assertEqual(template.bcc, '')
        self.assertEqual(template.cc, '')


class EmailNotificationModelTest(AsyncNotificationTestBase):

    def test_create_notification(self):
        notification = EmailNotification.objects.create(
            subject='Test Subject',
            message='<p>Test</p>',
            recipients='user@example.com'
        )
        self.assertEqual(notification.status, 'pending')
        self.assertFalse(notification.sent)
        self.assertTrue(notification.enqueued)
        self.assertFalse(notification.send_individually)
        self.assertEqual(notification.retry_count, 0)
        self.assertEqual(notification.error_message, '')

    def test_with_user(self):
        notification = EmailNotification.objects.create(
            subject='Test',
            message='msg',
            recipients='a@b.com',
            user=self.user
        )
        self.assertEqual(notification.user, self.user)

    def test_str_representation(self):
        notification = EmailNotification.objects.create(
            subject='Hello', message='m', recipients='r')
        self.assertEqual(str(notification), 'Hello (pending)')

    def test_status_choices(self):
        notification = EmailNotification.objects.create(
            subject='S', message='M', recipients='R')
        for status in ('pending', 'sending', 'sent', 'failed'):
            notification.status = status
            notification.save()
            notification.refresh_from_db()
            self.assertEqual(notification.status, status)


class AttachedFileModelTest(AsyncNotificationTestBase):

    def test_create_attached_file(self):
        notification = EmailNotification.objects.create(
            subject='S', message='M', recipients='R')
        ct = ContentType.objects.get_for_model(EmailNotification)
        attached = AttachedFile.objects.create(
            content_type=ct,
            object_id=notification.pk,
            file='test/file.pdf'
        )
        self.assertFalse(attached.is_inline)
        self.assertEqual(attached.content_id, '')
        self.assertEqual(attached.content_object, notification)

    def test_inline_attachment(self):
        notification = EmailNotification.objects.create(
            subject='S', message='M', recipients='R')
        ct = ContentType.objects.get_for_model(EmailNotification)
        attached = AttachedFile.objects.create(
            content_type=ct,
            object_id=notification.pk,
            file='test/image.png',
            is_inline=True,
            content_id='logo123'
        )
        self.assertTrue(attached.is_inline)
        self.assertEqual(attached.content_id, 'logo123')


class NewsLetterTemplateModelTest(AsyncNotificationTestBase):

    def test_create_newsletter_template(self):
        template = NewsLetterTemplate.objects.create(
            title='Monthly Update',
            slug='monthly-update',
            message='<p>Newsletter content</p>'
        )
        self.assertEqual(template.title, 'Monthly Update')
        self.assertEqual(template.model_base.count(), 0)

    def test_slug_uniqueness(self):
        NewsLetterTemplate.objects.create(
            title='First', slug='unique-slug', message='M')
        with self.assertRaises(IntegrityError):
            NewsLetterTemplate.objects.create(
                title='Second', slug='unique-slug', message='M2')

    def test_str_representation(self):
        template = NewsLetterTemplate.objects.create(
            title='My Newsletter', slug='my-news', message='M')
        self.assertEqual(str(template), 'My Newsletter')


class NewsLetterModelTest(AsyncNotificationTestBase):

    def test_create_newsletter(self):
        template = NewsLetterTemplate.objects.create(
            title='T', slug='t', message='M')
        newsletter = NewsLetter.objects.create(
            template=template,
            subject='Weekly Digest',
            message='<p>Digest content</p>',
            recipients='all@group.local',
            created_by=self.user
        )
        self.assertEqual(newsletter.subject, 'Weekly Digest')
        self.assertEqual(newsletter.template, template)
        self.assertEqual(newsletter.created_by, self.user)
        self.assertEqual(newsletter.bcc, '')
        self.assertEqual(newsletter.cc, '')

    def test_newsletter_without_template(self):
        newsletter = NewsLetter.objects.create(
            subject='No Template',
            message='M',
            recipients='R'
        )
        self.assertIsNone(newsletter.template)

    def test_str_representation(self):
        newsletter = NewsLetter.objects.create(
            subject='Test News', message='M', recipients='R')
        self.assertEqual(str(newsletter), 'Test News')


class NewsLetterTaskModelTest(AsyncNotificationTestBase):

    def test_create_task(self):
        newsletter = NewsLetter.objects.create(
            subject='S', message='M', recipients='R')
        task = NewsLetterTask.objects.create(
            newsletter=newsletter,
            send_date=timezone.now()
        )
        self.assertEqual(task.status, 'pending')
        self.assertIsNone(task.celery_task_id)
        self.assertEqual(task.newsletter, newsletter)

    def test_status_choices(self):
        newsletter = NewsLetter.objects.create(
            subject='S', message='M', recipients='R')
        task = NewsLetterTask.objects.create(
            newsletter=newsletter,
            send_date=timezone.now()
        )
        for status in ('pending', 'scheduled', 'sending',
                        'sent', 'failed', 'revoked'):
            task.status = status
            task.save()
            task.refresh_from_db()
            self.assertEqual(task.status, status)

    def test_str_representation(self):
        newsletter = NewsLetter.objects.create(
            subject='My News', message='M', recipients='R')
        send_date = timezone.now()
        task = NewsLetterTask.objects.create(
            newsletter=newsletter, send_date=send_date)
        self.assertIn('My News', str(task))
        self.assertIn('pending', str(task))
