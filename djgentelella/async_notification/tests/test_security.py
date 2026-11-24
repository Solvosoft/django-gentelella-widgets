"""
Who may link uploaded files to an object, read an attachment, or resolve a
``<pk>@<app>.<model>.internal`` address (W19).

On 73140ca0 ``reassociate_files_view`` linked the files of any upload
session to any object of any model -- an author of templates could add an
attachment to the email of somebody else's notification -- a user who only
viewed templates downloaded the attachments of notifications, and an author
previewing recipients read the email of any row of any model.
"""
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from demoapp.models import InputMask
from djgentelella.async_notification import views
from djgentelella.async_notification.models import (
    AttachedFile, EmailNotification, EmailTemplate, NewsLetter,
)
from djgentelella.async_notification.resolvers import (
    ContentTypeResolver, RecipientResolverRegistry, internal_model_allowed,
)
from djgentelella.async_notification.sending import _get_attachments


def perm_user(username, *codenames):
    user = User.objects.create_user(username, password='pw',
                                    email='%s@example.com' % username)
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(
            content_type__app_label='async_notification', codename=codename))
    return User.objects.get(pk=user.pk)


class FilesTestCase(TestCase):
    def tearDown(self):
        for attached in AttachedFile.objects.all():
            attached.file.delete(save=False)
        super().tearDown()

    def upload(self, session='s1', name='image.png'):
        response = self.client.post(reverse('async_notification:async_upload_image'), {
            'file': SimpleUploadedFile(name, b'\x89PNG data',
                                       content_type='image/png'),
            'upload_session': session})
        self.assertEqual(response.status_code, 200, response.content)
        return AttachedFile.objects.latest('pk')

    def reassociate(self, obj_id, session='s1',
                    content_type='async_notification.emailnotification'):
        return self.client.post(reverse('async_notification:reassociate_files'), {
            'upload_session': session, 'object_id': obj_id,
            'content_type': content_type})


@override_settings(LANGUAGE_CODE='en')
class ReassociateFilesTests(FilesTestCase):
    def setUp(self):
        self.victim = perm_user('victim', 'add_emailnotification')
        self.notification = EmailNotification.objects.create(
            subject='Victim', message='m', recipients=['a@example.com'],
            user=self.victim)

    def test_an_object_it_cannot_change_is_404(self):
        # The reproduction: on 73140ca0 this answered {"reassociated": 1} and
        # the file went out with the victim's email.
        self.client.force_login(perm_user('attacker', 'add_emailtemplate'))
        attached = self.upload()
        response = self.reassociate(self.notification.pk)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'error': 'Object not found'})
        attached.refresh_from_db()
        self.assertEqual(attached.object_id, 0)
        self.assertFalse(_get_attachments(self.notification).exists())

    def test_add_only_reaches_its_own_objects(self):
        author = perm_user('author', 'add_emailnotification')
        own = EmailNotification.objects.create(
            subject='Own', message='m', recipients=['a@example.com'], user=author)
        self.client.force_login(author)
        self.upload()
        self.assertEqual(self.reassociate(self.notification.pk).status_code, 404)
        self.assertEqual(self.reassociate(own.pk).json(), {'reassociated': 1})
        self.assertEqual(_get_attachments(own).count(), 1)

    def test_change_reaches_any_object_of_the_model(self):
        self.client.force_login(perm_user('editor', 'change_emailnotification'))
        self.upload()
        self.assertEqual(self.reassociate(self.notification.pk).json(),
                         {'reassociated': 1})
        self.assertEqual(_get_attachments(self.notification).count(), 1)

    def test_newsletters_and_templates(self):
        author = perm_user('author', 'add_newsletter', 'change_emailtemplate',
                           'add_newslettertemplate')
        self.client.force_login(author)
        newsletter = NewsLetter.objects.create(subject='N', created_by=author)
        theirs = NewsLetter.objects.create(subject='T', created_by=self.victim)
        template = EmailTemplate.objects.create(code='w19', subject='S',
                                                message='m')
        self.upload('n')
        self.upload('t')
        self.assertEqual(self.reassociate(
            theirs.pk, 'n', 'async_notification.newsletter').status_code, 404)
        self.assertEqual(self.reassociate(
            newsletter.pk, 'n', 'async_notification.newsletter').json(),
            {'reassociated': 1})
        self.assertEqual(self.reassociate(
            template.pk, 't', 'async_notification.emailtemplate').json(),
            {'reassociated': 1})

    def test_only_models_of_the_module(self):
        self.client.force_login(perm_user('editor', 'change_emailnotification'))
        attached = self.upload()
        for content_type in ('auth.user', 'demoapp.inputmask',
                             'async_notification.attachedfile',
                             'async_notification.emailsuppression', 'nonsense'):
            response = self.reassociate(self.victim.pk, content_type=content_type)
            self.assertEqual(response.status_code, 400, content_type)
            self.assertEqual(response.json(), {'error': 'Invalid content_type'})
        attached.refresh_from_db()
        self.assertEqual(attached.object_id, 0)

    def test_a_missing_or_invalid_object_is_404(self):
        self.client.force_login(perm_user('editor', 'change_emailnotification'))
        self.upload()
        for object_id in ('999999', '0', '-1', 'abc', '1 OR 1=1'):
            self.assertEqual(self.reassociate(object_id).status_code, 404, object_id)

    def test_only_its_own_uploads_move(self):
        # Somebody else uploaded with the same upload_session.
        self.client.force_login(perm_user('author', 'add_emailnotification'))
        foreign = self.upload('shared')
        self.client.force_login(perm_user('editor', 'change_emailnotification'))
        mine = self.upload('shared')
        self.assertEqual(self.reassociate(self.notification.pk, 'shared').json(),
                         {'reassociated': 1})
        foreign.refresh_from_db()
        mine.refresh_from_db()
        self.assertEqual(foreign.object_id, 0)
        self.assertEqual(mine.object_id, self.notification.pk)
        # The session is consumed.
        self.assertEqual(self.reassociate(self.notification.pk, 'shared').json(),
                         {'reassociated': 0})

    def test_the_session_keeps_the_last_upload_sessions(self):
        request = RequestFactory().post('/')
        request.session = {}
        for number in range(views.MAX_UPLOAD_SESSIONS + 5):
            views._remember_upload(request, 's%d' % number,
                                   type('A', (), {'pk': number}))
        sessions = request.session[views.UPLOADS_SESSION_KEY]
        self.assertEqual(len(sessions), views.MAX_UPLOAD_SESSIONS)
        self.assertNotIn('s0', sessions)
        self.assertEqual(sessions['s24'], [24])
        views._remember_upload(request, '', type('A', (), {'pk': 99}))
        self.assertNotIn('', request.session[views.UPLOADS_SESSION_KEY])


class PreviewFileTests(FilesTestCase):
    def setUp(self):
        self.notification = EmailNotification.objects.create(
            subject='Invoice', message='m', recipients=['a@example.com'])
        ct = ContentType.objects.get_for_model(EmailNotification)
        self.attachment = AttachedFile.objects.create(
            content_type=ct, object_id=self.notification.pk,
            file=SimpleUploadedFile('invoice.pdf', b'%PDF private'))
        template = EmailTemplate.objects.create(code='w19', subject='S', message='m')
        self.inline = AttachedFile.objects.create(
            content_type=ContentType.objects.get_for_model(EmailTemplate),
            object_id=template.pk, is_inline=True,
            file=SimpleUploadedFile('logo.png', b'\x89PNG logo'))
        self.pending = AttachedFile.objects.create(
            content_type=ct, object_id=0,
            file=SimpleUploadedFile('new.png', b'\x89PNG new'))

    def get(self, attached):
        return self.client.get(reverse('async_notification:preview_file',
                                       args=[attached.pk]))

    def test_an_attachment_needs_the_object(self):
        # The reproduction: on 73140ca0 a template viewer got the invoice.
        self.client.force_login(perm_user('reader', 'view_emailtemplate'))
        self.assertEqual(self.get(self.attachment).status_code, 404)
        self.client.force_login(perm_user('viewer', 'view_emailnotification'))
        response = self.get(self.attachment)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'%PDF private')
        self.client.force_login(perm_user('editor', 'change_emailnotification'))
        self.assertEqual(self.get(self.attachment).status_code, 200)

    def test_inline_images_and_pending_uploads_as_before(self):
        # A notification rendered from a template shows the template's images.
        self.client.force_login(perm_user('viewer', 'view_emailnotification'))
        self.assertEqual(self.get(self.inline).status_code, 200)
        self.assertEqual(self.get(self.pending).status_code, 200)

    def test_an_attachment_of_a_deleted_object(self):
        self.client.force_login(perm_user('viewer', 'view_emailnotification'))
        EmailNotification.objects.filter(pk=self.notification.pk).delete()
        self.assertEqual(self.get(self.attachment).status_code, 404)

    def test_an_attachment_of_a_model_that_is_gone(self):
        self.client.force_login(perm_user('viewer', 'view_emailnotification'))
        gone = ContentType.objects.create(app_label='gone', model='gone')
        AttachedFile.objects.filter(pk=self.attachment.pk).update(content_type=gone)
        self.assertEqual(self.get(self.attachment).status_code, 404)

    def test_without_any_permission_still_403(self):
        self.client.force_login(User.objects.create_user('nobody'))
        self.assertEqual(self.get(self.pending).status_code, 403)


class InternalAddressTests(TestCase):
    def setUp(self):
        RecipientResolverRegistry.register('internal', ContentTypeResolver)
        self.row = InputMask.objects.create(email='private@example.com',
                                            date='2026-01-01')
        self.address = '%d@demoapp.inputmask.internal' % self.row.pk

    def preview(self, recipients):
        response = self.client.post(
            reverse('async_notification:newsletter_recipients_preview'),
            {'recipients': recipients})
        self.assertEqual(response.status_code, 200)
        return response.json()['recipients']

    def test_any_model_with_an_email_does_not_resolve(self):
        # The reproduction: on 73140ca0 the preview showed private@example.com.
        self.client.force_login(perm_user('author', 'add_newsletter'))
        self.assertEqual(self.preview(self.address), [])
        self.assertEqual(RecipientResolverRegistry.resolve(self.address), [])

    @override_settings(ASYNC_NOTIFICATION_INTERNAL_MODELS=['demoapp.InputMask'])
    def test_a_model_listed_in_the_setting(self):
        self.assertTrue(internal_model_allowed(InputMask))
        self.assertEqual(RecipientResolverRegistry.resolve(self.address),
                         ['private@example.com'])

    def test_the_user_model_and_gt_get_mail_address(self):
        user = perm_user('author', 'add_newsletter')
        self.client.force_login(user)
        self.assertEqual(self.preview('%d@auth.user.internal' % user.pk),
                         ['author@example.com'])

        class Addressed:
            def gt_get_mail_address(self):
                return ''
        self.assertTrue(internal_model_allowed(Addressed))
        self.assertFalse(internal_model_allowed(InputMask))
