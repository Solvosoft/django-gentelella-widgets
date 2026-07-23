from django import forms
from django.contrib.auth import get_user_model

from djgentelella.async_notification.tests import AsyncNotificationTestBase
from djgentelella.async_notification.interfaces import (
    NewsLetterInterface, register_news_basemodel, get_basemodel_info,
    get_basemodels_dict, clear_basemodels,
)
from djgentelella.async_notification.models import (
    NewsLetter, NewsLetterTemplate,
)
from djgentelella.async_notification.sending import (
    compute_newsletter_recipients,
)

User = get_user_model()


class UserFilterForm(forms.Form):
    is_active = forms.BooleanField(required=False)
    excludeemail = forms.CharField(required=False)


class UserInterface(NewsLetterInterface):
    name = 'users'
    form = UserFilterForm
    model = User
    email_field = 'email'
    field_map = {
        'filter': {'is_active': 'is_active'},
        'exclude': {'excludeemail': 'email__in'},
    }


class NewsLetterInterfaceTest(AsyncNotificationTestBase):

    def test_get_recipients_all(self):
        emails = UserInterface().get_recipients('')
        self.assertIn('admin@example.com', emails)
        self.assertIn('testuser@example.com', emails)
        self.assertIn('noperms@example.com', emails)

    def test_get_recipients_filtered(self):
        User.objects.filter(username='noperms').update(is_active=False)
        emails = UserInterface().get_recipients('is_active=on')
        self.assertIn('testuser@example.com', emails)
        self.assertNotIn('noperms@example.com', emails)

    def test_get_recipients_exclude(self):
        emails = UserInterface().get_recipients(
            'excludeemail=admin@example.com')
        self.assertNotIn('admin@example.com', emails)
        self.assertIn('testuser@example.com', emails)

    def test_get_recipients_no_model(self):
        self.assertEqual(NewsLetterInterface().get_recipients(''), [])


class BaseModelRegistryTest(AsyncNotificationTestBase):

    def tearDown(self):
        clear_basemodels()

    def test_register_and_lookup(self):
        register_news_basemodel('users', 'Users', UserInterface)
        info = get_basemodel_info('users')
        self.assertEqual(info[2], UserInterface)
        self.assertIn(('users', 'Users'), get_basemodels_dict())

    def test_register_by_dotted_path(self):
        path = ('djgentelella.async_notification.tests.'
                'test_interfaces.UserInterface')
        register_news_basemodel('users', 'Users', path)
        self.assertEqual(get_basemodel_info('users')[2], UserInterface)

    def test_unknown_key(self):
        self.assertIsNone(get_basemodel_info('missing'))


class ComputeNewsletterRecipientsTest(AsyncNotificationTestBase):

    def tearDown(self):
        clear_basemodels()

    def test_merges_free_text_and_interface(self):
        register_news_basemodel('users', 'Users', UserInterface)
        template = NewsLetterTemplate.objects.create(
            title='T', slug='t', message='M', model_base='users')
        newsletter = NewsLetter.objects.create(
            subject='S', message='M', template=template,
            recipients=['extra@x.com'],
            filters_querystring='excludeemail=admin@example.com')
        emails = compute_newsletter_recipients(newsletter)
        self.assertIn('extra@x.com', emails)
        self.assertIn('testuser@example.com', emails)
        self.assertNotIn('admin@example.com', emails)

    def test_free_text_address_of_the_base_model_still_respects_filters(self):
        """A free-text entry that resolves to a base-model address (e.g. a
        Django group full of ``auth.User`` emails via ``@group.local``) must
        still honor is_active/exclude, not bypass them just because it
        arrived through the free-text field instead of the interface."""
        register_news_basemodel('users', 'Users', UserInterface)
        User.objects.filter(username='noperms').update(is_active=False)
        template = NewsLetterTemplate.objects.create(
            title='T', slug='t2', message='M', model_base='users')
        newsletter = NewsLetter.objects.create(
            subject='S', message='M', template=template,
            # Both typed directly, as if resolved from a group: one
            # excluded, one inactive, one an external (non-User) address.
            recipients=['admin@example.com', 'noperms@example.com',
                       'external@nowhere.com'],
            filters_querystring='is_active=on&excludeemail=admin@example.com')
        emails = compute_newsletter_recipients(newsletter)
        self.assertNotIn('admin@example.com', emails)
        self.assertNotIn('noperms@example.com', emails)
        self.assertIn('external@nowhere.com', emails)
        self.assertIn('testuser@example.com', emails)

    def test_no_model_base_uses_free_text_only(self):
        template = NewsLetterTemplate.objects.create(
            title='T', slug='t', message='M')
        newsletter = NewsLetter.objects.create(
            subject='S', message='M', template=template,
            recipients=['only@x.com'])
        self.assertEqual(
            compute_newsletter_recipients(newsletter), ['only@x.com'])
