"""
Management command to generate demo data for async_notification models.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from djgentelella.async_notification.models import (
    EmailTemplate, EmailNotification,
    NewsLetterTemplate, NewsLetter, NewsLetterTask
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate demo data for async_notification models.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Clear existing async_notification data before creating')
        parser.add_argument(
            '--user', type=str, default='',
            help='Username to associate with notifications')

    def handle(self, *args, **options):
        if options['clear']:
            self._clear_data()

        user = None
        if options['user']:
            try:
                user = User.objects.get(username=options['user'])
            except User.DoesNotExist:
                self.stderr.write(
                    f'User "{options["user"]}" not found, '
                    f'proceeding without user association.')

        self._create_email_templates()
        self._create_email_notifications(user)
        self._create_newsletter_templates()
        self._create_newsletters(user)
        self._create_newsletter_tasks()

        self.stdout.write(self.style.SUCCESS(
            'Demo notification data created successfully.'))

    def _clear_data(self):
        NewsLetterTask.objects.all().delete()
        NewsLetter.objects.all().delete()
        NewsLetterTemplate.objects.all().delete()
        EmailNotification.objects.all().delete()
        EmailTemplate.objects.all().delete()
        self.stdout.write('Cleared existing async_notification data.')

    def _create_email_templates(self):
        templates = [
            {
                'code': 'welcome',
                'subject': 'Welcome to our platform, {{ user.first_name }}!',
                'message': (
                    '<h2>Welcome, {{ user.first_name }}!</h2>'
                    '<p>Thank you for joining our platform. '
                    'Your account <strong>{{ user.username }}</strong> '
                    'is now active.</p>'
                    '<p>Get started by exploring our features.</p>'
                ),
            },
            {
                'code': 'password-reset',
                'subject': 'Password Reset Request',
                'message': (
                    '<h2>Password Reset</h2>'
                    '<p>Hello {{ user.first_name }},</p>'
                    '<p>We received a request to reset your password. '
                    'Click the link below to proceed:</p>'
                    '<p><a href="{{ reset_url }}">Reset Password</a></p>'
                    '<p>If you did not request this, please ignore '
                    'this email.</p>'
                ),
            },
            {
                'code': 'order-confirmation',
                'subject': 'Order #{{ order.id }} Confirmed',
                'message': (
                    '<h2>Order Confirmation</h2>'
                    '<p>Dear {{ user.first_name }},</p>'
                    '<p>Your order <strong>#{{ order.id }}</strong> '
                    'has been confirmed.</p>'
                    '<p>Total: ${{ order.total }}</p>'
                    '<p>Estimated delivery: {{ order.delivery_date }}</p>'
                    '<p>Thank you for your purchase!</p>'
                ),
            },
        ]
        for data in templates:
            EmailTemplate.objects.update_or_create(
                code=data['code'],
                defaults={
                    'subject': data['subject'],
                    'message': data['message'],
                }
            )
        self.stdout.write(f'  Created {len(templates)} email templates.')

    def _create_email_notifications(self, user):
        statuses = ['pending', 'sending', 'sent', 'failed']
        for status in statuses:
            EmailNotification.objects.create(
                subject=f'Demo notification ({status})',
                message=f'<p>This is a demo notification with status: '
                        f'<strong>{status}</strong>.</p>',
                recipients='admin@example.com, user@example.com',
                status=status,
                sent=(status == 'sent'),
                enqueued=True,
                user=user,
                error_message=(
                    'SMTP connection refused' if status == 'failed' else ''
                ),
                retry_count=(3 if status == 'failed' else 0),
            )
        self.stdout.write(
            f'  Created {len(statuses)} email notifications.')

    def _create_newsletter_templates(self):
        templates = [
            {
                'title': 'Monthly Digest',
                'slug': 'monthly-digest',
                'message': (
                    '<h1>Monthly Digest</h1>'
                    '<p>Here are the highlights from this month:</p>'
                    '<ul>'
                    '<li>New features released</li>'
                    '<li>Community updates</li>'
                    '<li>Upcoming events</li>'
                    '</ul>'
                ),
            },
            {
                'title': 'Product Announcement',
                'slug': 'product-announcement',
                'message': (
                    '<h1>Exciting Product Announcement!</h1>'
                    '<p>We are thrilled to announce our latest product.</p>'
                    '<p>Stay tuned for more details.</p>'
                ),
            },
        ]
        for data in templates:
            NewsLetterTemplate.objects.update_or_create(
                slug=data['slug'],
                defaults={
                    'title': data['title'],
                    'message': data['message'],
                }
            )
        self.stdout.write(
            f'  Created {len(templates)} newsletter templates.')

    def _create_newsletters(self, user):
        digest = NewsLetterTemplate.objects.filter(
            slug='monthly-digest').first()
        announcement = NewsLetterTemplate.objects.filter(
            slug='product-announcement').first()

        for tpl, subject, recipients in [
            (digest, 'January 2026 Monthly Digest',
             'subscribers@group.local'),
            (announcement, 'New Product Launch Q1 2026',
             'all-users@group.local, vip@group.local'),
        ]:
            NewsLetter.objects.update_or_create(
                subject=subject,
                defaults={
                    'template': tpl,
                    'message': tpl.message if tpl else '<p>Newsletter</p>',
                    'recipients': recipients,
                    'created_by': user,
                }
            )
        self.stdout.write('  Created 2 newsletters.')

    def _create_newsletter_tasks(self):
        newsletters = NewsLetter.objects.all()[:2]
        statuses = ['pending', 'scheduled', 'sent', 'failed']
        now = timezone.now()
        count = 0
        for newsletter in newsletters:
            for i, status in enumerate(statuses):
                NewsLetterTask.objects.create(
                    newsletter=newsletter,
                    send_date=now + timezone.timedelta(days=i),
                    status=status,
                )
                count += 1
        self.stdout.write(f'  Created {count} newsletter tasks.')
