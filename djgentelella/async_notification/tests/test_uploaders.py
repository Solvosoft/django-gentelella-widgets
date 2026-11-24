"""Who takes over a pending upload, how videos are served and how a file name
reaches ``Content-Disposition`` (W20, the residuals of W19).

On 4faeda00 saving a body that named the pk of somebody else's pending image
linked that image to the new object (``link_body_attachments`` did not look at
who uploaded it), a video upload answered its ``MEDIA_URL`` -- served wherever
the project serves media, outside any view with permissions -- and
``preview_file_view`` pasted the stored name between quotes in
``Content-Disposition``.
"""
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils.http import content_disposition_header

from djgentelella.async_notification.models import (
    AttachedFile, EmailNotification, EmailTemplate,
)
from djgentelella.async_notification.sending import link_body_attachments
from djgentelella.async_notification.tests.test_security import (
    FilesTestCase, perm_user,
)

AUTHOR_PERMS = ('add_emailnotification', 'view_emailnotification')


def body_with(attached):
    url = reverse('async_notification:preview_file', args=[attached.pk])
    return '<p>Hi</p><img src="%s">' % url


@override_settings(LANGUAGE_CODE='en')
class LinkBodyAttachmentsTests(FilesTestCase):
    def setUp(self):
        self.victim = perm_user('victim', *AUTHOR_PERMS)
        self.attacker = perm_user('attacker', *AUTHOR_PERMS)

    def create_notification(self, message):
        url = reverse('async_notification:api-emailnotification-list')
        response = self.client.post(url, {
            'subject': 'S', 'message': message,
            'recipients': ['a@example.com'], 'enqueued': False,
            'send_individually': False,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        return EmailNotification.objects.latest('pk')

    def test_a_body_does_not_take_over_somebody_elses_upload(self):
        # The reproduction: on 4faeda00 the victim's pending image ended up
        # linked to the attacker's notification.
        self.client.force_login(self.victim)
        pending = self.upload(session='victim')
        self.client.force_login(self.attacker)
        self.create_notification(body_with(pending))
        pending.refresh_from_db()
        self.assertEqual(pending.object_id, 0)

    def test_its_own_upload_is_linked(self):
        self.client.force_login(self.victim)
        pending = self.upload(session='own')
        self.assertEqual(pending.uploaded_by, self.victim)
        notification = self.create_notification(body_with(pending))
        pending.refresh_from_db()
        self.assertEqual(pending.object_id, notification.pk)
        self.assertEqual(pending.content_type,
                         ContentType.objects.get_for_model(EmailNotification))

    def test_without_a_user_only_uploads_without_an_uploader(self):
        ct = ContentType.objects.get_for_model(EmailNotification)
        orphan = AttachedFile.objects.create(
            content_type=ct, object_id=0, is_inline=True,
            file=SimpleUploadedFile('a.png', b'\x89PNG a'))
        owned = AttachedFile.objects.create(
            content_type=ct, object_id=0, is_inline=True, uploaded_by=self.victim,
            file=SimpleUploadedFile('b.png', b'\x89PNG b'))
        template = EmailTemplate.objects.create(
            code='w20', subject='S', message=body_with(orphan) + body_with(owned))
        link_body_attachments(template)
        orphan.refresh_from_db()
        owned.refresh_from_db()
        self.assertEqual(orphan.object_id, template.pk)
        self.assertEqual(owned.object_id, 0)

    def test_reassociation_only_moves_its_own_uploads(self):
        self.client.force_login(self.victim)
        pending = self.upload(session='shared')
        own = EmailNotification.objects.create(
            subject='Own', message='m', recipients=['a@example.com'],
            user=self.victim)
        # Somebody else's file under the same upload session and in the
        # victim's session list: still not the victim's to move.
        AttachedFile.objects.filter(pk=pending.pk).update(uploaded_by=self.attacker)
        response = self.reassociate(own.pk, session='shared')
        self.assertEqual(response.json(), {'reassociated': 0})


@override_settings(LANGUAGE_CODE='en')
class VideoTests(FilesTestCase):
    def upload_video(self, name='clip.mp4'):
        response = self.client.post(
            reverse('async_notification:async_upload_video'),
            {'file': SimpleUploadedFile(name, b'\x00\x00\x00\x18ftypmp42',
                                        content_type='video/mp4'),
             'upload_session': 'v1'})
        self.assertEqual(response.status_code, 200, response.content)
        return AttachedFile.objects.latest('pk'), response.json()

    def test_the_link_is_a_view_not_the_media_url(self):
        # The reproduction: on 4faeda00 the link was attached.file.url.
        self.client.force_login(perm_user('author', *AUTHOR_PERMS))
        attached, data = self.upload_video()
        url = reverse('async_notification:preview_video', args=[attached.pk])
        self.assertEqual(data, {'link': url, 'location': url})
        self.assertNotIn(attached.file.name, data['link'])

    def test_the_view_serves_the_video_with_permissions(self):
        self.client.force_login(perm_user('author', *AUTHOR_PERMS))
        attached, data = self.upload_video()
        response = self.client.get(data['link'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'video/mp4')
        self.assertEqual(b''.join(response.streaming_content),
                         b'\x00\x00\x00\x18ftypmp42')
        self.client.logout()
        self.assertEqual(self.client.get(data['link']).status_code, 302)
        self.client.force_login(perm_user('nobody'))
        self.assertEqual(self.client.get(data['link']).status_code, 403)

    def test_a_video_of_a_notification_needs_the_notification(self):
        author = perm_user('author', *AUTHOR_PERMS)
        self.client.force_login(author)
        attached, data = self.upload_video()
        notification = EmailNotification.objects.create(
            subject='S', message='<video src="%s"></video>' % data['link'],
            recipients=['a@example.com'], user=author)
        link_body_attachments(notification, user=author)
        attached.refresh_from_db()
        self.assertEqual(attached.object_id, notification.pk)
        self.client.force_login(perm_user('reader', 'view_emailtemplate'))
        self.assertEqual(self.client.get(data['link']).status_code, 404)

    def test_a_name_that_is_not_a_video_is_served_as_bytes(self):
        self.client.force_login(perm_user('author', *AUTHOR_PERMS))
        attached, data = self.upload_video(name='page.html')
        response = self.client.get(data['link'])
        self.assertEqual(response['Content-Type'], 'application/octet-stream')

    def test_an_inline_image_is_not_a_video(self):
        self.client.force_login(perm_user('author', *AUTHOR_PERMS))
        image = self.upload(session='i1')
        response = self.client.get(
            reverse('async_notification:preview_video', args=[image.pk]))
        self.assertEqual(response.status_code, 404)


@override_settings(LANGUAGE_CODE='en')
class ContentDispositionTests(FilesTestCase):
    def stored(self, name):
        # Saved by the storage itself: upload_to would have cleaned the name.
        path = default_storage.save('async_notification/w20/' + name,
                                    ContentFile(b'\x89PNG x'))
        return AttachedFile.objects.create(
            content_type=ContentType.objects.get_for_model(EmailNotification),
            object_id=0, is_inline=True, file=path)

    def get(self, attached):
        self.client.force_login(perm_user('author', *AUTHOR_PERMS))
        return self.client.get(
            reverse('async_notification:preview_file', args=[attached.pk]))

    def test_a_quote_in_the_name_is_escaped(self):
        # The reproduction: on 4faeda00 the header was
        # inline; filename="async_notification/w20/a"; x=".png".
        response = self.get(self.stored('a"; x=.png'))
        self.assertEqual(response['Content-Disposition'],
                         content_disposition_header(False, 'a"; x=.png'))
        self.assertEqual(response['Content-Disposition'],
                         'inline; filename="a\\"; x=.png"')

    def test_a_name_that_is_not_ascii(self):
        response = self.get(self.stored('café.png'))
        self.assertEqual(response['Content-Disposition'],
                         "inline; filename*=utf-8''caf%C3%A9.png")
