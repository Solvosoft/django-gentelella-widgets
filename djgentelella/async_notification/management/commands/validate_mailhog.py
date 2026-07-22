"""
End-to-end email validation against a MailHog receiver.

Exercises every implemented sending feature (basic sends, batching,
send-individually, template rendering with context, base-template wrapping,
inline cid images, file attachments, newsletters with model-base filters,
retry-then-success, and idempotency/no-duplicates) by sending real emails
over SMTP to MailHog, then validating reception through the MailHog API.

Usage:
    make mailhog            # start the receiver (SMTP :1025, UI :8025)
    cd demo && python manage.py validate_mailhog
"""

import base64
import json
import logging
import time
import urllib.request
from email import message_from_string

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone

from djgentelella.async_notification.models import (
    AttachedFile, EmailNotification, EmailTemplate,
    NewsLetter, NewsLetterTemplate, NewsLetterTask,
)
from djgentelella.async_notification.sending import (
    do_send_notification, do_send_newsletter, send_email_from_template,
    compute_newsletter_recipients,
)

TAG = '[MHTEST]'
PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAE'
    'hQGAhKmMIQAAAABJRU5ErkJggg==')
User = get_user_model()


class Command(BaseCommand):
    help = 'Validate all email features against a MailHog receiver.'

    def add_arguments(self, parser):
        parser.add_argument('--smtp-host', default='localhost')
        parser.add_argument('--smtp-port', default='1025')
        parser.add_argument('--api', default='http://localhost:8025')
        parser.add_argument(
            '--keep', action='store_true',
            help='Keep the created DB rows (default deletes them).')

    # -- MailHog API helpers -------------------------------------------------
    def mh_reset(self):
        req = urllib.request.Request(
            f'{self.api}/api/v1/messages', method='DELETE')
        urllib.request.urlopen(req, timeout=10).read()

    def mh_messages(self):
        with urllib.request.urlopen(
                f'{self.api}/api/v2/messages?limit=1000', timeout=10) as resp:
            data = json.loads(resp.read().decode())
        out = []
        for item in data.get('items', []):
            headers = item['Content']['Headers']
            raw = ''
            try:
                raw = item['Raw']['Data']
            except (KeyError, TypeError):
                pass
            out.append({
                'subject': (headers.get('Subject') or [''])[0],
                'to': item.get('Raw', {}).get('To') or [],
                'message_id': (headers.get('Message-ID') or [''])[0],
                'raw': raw,
                'decoded': self._decoded_body(raw),
            })
        return out

    @staticmethod
    def _decoded_body(raw):
        """Return the concatenated decoded text of all message parts."""
        try:
            msg = message_from_string(raw)
        except Exception:
            return raw
        chunks = []
        for part in msg.walk():
            if part.is_multipart():
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            try:
                chunks.append(payload.decode(
                    part.get_content_charset() or 'utf-8', 'replace'))
            except Exception:
                chunks.append(str(payload))
        return '\n'.join(chunks)

    # -- assertion helpers ---------------------------------------------------
    def _for(self, subject):
        return [m for m in self._messages if m['subject'] == subject]

    def expect(self, name, condition, detail=''):
        self._results.append((name, bool(condition), detail))

    def check_recipients(self, name, subject, expected):
        msgs = self._for(subject)
        deliveries = [addr for m in msgs for addr in m['to']]
        got = set(deliveries)
        no_dupes = len(deliveries) == len(got)
        self.expect(
            f'{name}: recipients',
            got == set(expected) and no_dupes,
            f'expected={sorted(expected)} got={sorted(got)} '
            f'deliveries={len(deliveries)} dupes={not no_dupes}')

    def check_body(self, name, subject, needle, present=True):
        msgs = self._for(subject)
        found = any(needle in m['decoded'] or needle in m['raw']
                    for m in msgs)
        self.expect(f'{name}: {"has" if present else "no"} "{needle}"',
                    found == present)

    # -- SMTP config ---------------------------------------------------------
    def use_smtp(self, port):
        settings.EMAIL_BACKEND = \
            'django.core.mail.backends.smtp.EmailBackend'
        settings.EMAIL_HOST = self.smtp_host
        settings.EMAIL_PORT = str(port)

    # -- lifecycle -----------------------------------------------------------
    def cleanup(self):
        EmailNotification.objects.filter(subject__startswith=TAG).delete()
        NewsLetter.objects.filter(subject__startswith=TAG).delete()
        NewsLetterTemplate.objects.filter(title__startswith=TAG).delete()
        EmailTemplate.objects.filter(code__startswith='mhtest-').delete()
        AttachedFile.objects.filter(content_id='mhtest').delete()
        User.objects.filter(username__startswith='mhtest_').delete()

    def handle(self, *args, **options):
        self.smtp_host = options['smtp_host']
        self.api = options['api'].rstrip('/')
        self._results = []
        started = time.time()

        self.use_smtp(options['smtp_port'])
        self.cleanup()
        self.mh_reset()
        self.stdout.write(self.style.MIGRATE_HEADING(
            'Sending scenarios to MailHog...'))

        self.scenario_basic()
        self.scenario_batch()
        self.scenario_individual()
        self.scenario_template_context()
        self.scenario_base_template()
        self.scenario_inline_image()
        self.scenario_attachment()
        self.scenario_newsletter()
        self.scenario_newsletter_filtered()
        self.scenario_retry_then_success(options['smtp_port'])
        self.scenario_idempotency()

        # Give MailHog a moment, then fetch once.
        self._messages = self.mh_messages()
        self.validate()
        self.report(time.time() - started)

        if not options['keep']:
            self.cleanup()

    # -- scenarios -----------------------------------------------------------
    def scenario_basic(self):
        n = EmailNotification.objects.create(
            subject=f'{TAG} Basic', message='<p>Hello Basic</p>',
            recipients=['one@example.com'])
        do_send_notification(n.pk)
        self._basic_pk = n.pk

    def scenario_batch(self):
        n = EmailNotification.objects.create(
            subject=f'{TAG} Batch', message='<p>Batch body</p>',
            recipients=['b1@example.com', 'b2@example.com', 'b3@example.com'])
        do_send_notification(n.pk)

    def scenario_individual(self):
        n = EmailNotification.objects.create(
            subject=f'{TAG} Individual', message='<p>Solo</p>',
            recipients=['i1@example.com', 'i2@example.com', 'i3@example.com'],
            send_individually=True)
        do_send_notification(n.pk)

    def scenario_template_context(self):
        EmailTemplate.objects.create(
            code='mhtest-welcome',
            subject=f'{TAG} Hi {{{{ user.first_name }}}}',
            message='<p>Dear {{ user.first_name }} {{ user.last_name }}</p>')
        n = send_email_from_template(
            'mhtest-welcome', 'ctx@example.com',
            {'user': {'first_name': 'Ada', 'last_name': 'Lovelace'}})
        do_send_notification(n.pk)

    def scenario_base_template(self):
        n = EmailNotification.objects.create(
            subject=f'{TAG} Base', message='<p>S5 wrapped body</p>',
            recipients=['base@example.com'], base_template='default')
        do_send_notification(n.pk)

    def scenario_inline_image(self):
        att = AttachedFile.objects.create(
            content_type=ContentType.objects.get_for_model(EmailNotification),
            object_id=0, is_inline=True, content_id='mhtest',
            file=ContentFile(PNG, name='inline.png'))
        n = EmailNotification.objects.create(
            subject=f'{TAG} Inline', recipients=['inline@example.com'],
            message=(f'<p><img src="/async_notification/preview-file/'
                     f'{att.pk}/"></p>'))
        self._inline_pk = att.pk
        do_send_notification(n.pk)

    def scenario_attachment(self):
        n = EmailNotification.objects.create(
            subject=f'{TAG} Attach', message='<p>See attachment</p>',
            recipients=['attach@example.com'])
        att = AttachedFile.objects.create(
            content_type=ContentType.objects.get_for_model(EmailNotification),
            object_id=n.pk, is_inline=False, content_id='mhtest',
            file=ContentFile(b'report data', name='report.txt'))
        # Storage may append a suffix on name collisions; use the real name.
        self._attach_name = att.file.name.rsplit('/', 1)[-1]
        do_send_notification(n.pk)

    def scenario_newsletter(self):
        nl = NewsLetter.objects.create(
            subject=f'{TAG} News', message='<p>Newsletter body</p>',
            recipients=['n1@example.com', 'n2@example.com'],
            base_template='default')
        task = NewsLetterTask.objects.create(
            newsletter=nl, send_date=timezone.now(), status='pending')
        do_send_newsletter(task.pk)

    def scenario_newsletter_filtered(self):
        for i, active in enumerate([True, True, False]):
            User.objects.create_user(
                username=f'mhtest_u{i}', email=f'mhu{i}@example.com',
                password='x', is_active=active)
        nl = NewsLetter.objects.create(
            subject=f'{TAG} NewsFilter', message='<p>Filtered</p>',
            recipients=['extra@example.com'])
        template = NewsLetterTemplate.objects.create(
            title=f'{TAG} FilterTpl', slug='mhtest-filter', message='m',
            model_base='users')
        nl.template = template
        nl.filters_querystring = 'is_active=on&excludeemail=mhu1@example.com'
        nl.save()
        self._filtered_expected = set(compute_newsletter_recipients(nl))
        task = NewsLetterTask.objects.create(
            newsletter=nl, send_date=timezone.now(), status='pending')
        do_send_newsletter(task.pk)

    def scenario_retry_then_success(self, good_port):
        n = EmailNotification.objects.create(
            subject=f'{TAG} Retry', message='<p>Retry body</p>',
            recipients=['retry@example.com'], max_retries=3)
        # First attempt against a closed port -> failure + retry. Silence the
        # expected connection-refused traceback the sender logs.
        logging.disable(logging.CRITICAL)
        try:
            self.use_smtp('1')
            do_send_notification(n.pk)
        finally:
            logging.disable(logging.NOTSET)
        n.refresh_from_db()
        self._retry_after_fail = (n.status, n.retry_count)
        # Restore and send successfully.
        self.use_smtp(good_port)
        do_send_notification(n.pk)
        n.refresh_from_db()
        self._retry_final = (n.status, n.retry_count)

    def scenario_idempotency(self):
        # Re-sending the already-sent basic notification must not duplicate.
        do_send_notification(self._basic_pk)
        # A queued notification processed by the cron command; running it
        # twice must send exactly one email. Isolate from unrelated pending
        # rows so only this one is picked up.
        others = list(EmailNotification.objects.filter(
            status__in=('pending', 'queued'), enqueued=True
        ).exclude(subject__startswith=TAG).values_list('pk', flat=True))
        EmailNotification.objects.filter(pk__in=others).update(enqueued=False)
        try:
            EmailNotification.objects.create(
                subject=f'{TAG} Queue', message='<p>Queued</p>',
                recipients=['queue@example.com'], enqueued=True,
                status='pending')
            call_command('process_notifications')
            call_command('process_notifications')
        finally:
            EmailNotification.objects.filter(pk__in=others).update(
                enqueued=True)

    # -- validation ----------------------------------------------------------
    def validate(self):
        self.check_recipients('basic', f'{TAG} Basic', ['one@example.com'])
        self.check_body('basic', f'{TAG} Basic', 'Hello Basic')

        self.expect('batch: single email', len(self._for(f'{TAG} Batch')) == 1,
                    f'msgs={len(self._for(f"{TAG} Batch"))}')
        self.check_recipients('batch', f'{TAG} Batch',
                              ['b1@example.com', 'b2@example.com',
                               'b3@example.com'])

        self.expect('individual: one per recipient',
                    len(self._for(f'{TAG} Individual')) == 3,
                    f'msgs={len(self._for(f"{TAG} Individual"))}')
        self.check_recipients('individual', f'{TAG} Individual',
                              ['i1@example.com', 'i2@example.com',
                               'i3@example.com'])

        self.expect('template: subject rendered',
                    len(self._for(f'{TAG} Hi Ada')) == 1)
        self.check_body('template', f'{TAG} Hi Ada', 'Dear Ada Lovelace')
        self.check_body('template', f'{TAG} Hi Ada', '{{', present=False)

        self.check_body('base_template', f'{TAG} Base', 'async-email-body')
        self.check_body('base_template', f'{TAG} Base', 'S5 wrapped body')

        self.check_body('inline', f'{TAG} Inline',
                        f'cid:img_{self._inline_pk}')
        self.check_body('inline', f'{TAG} Inline',
                        f'img_{self._inline_pk}')

        self.check_body('attachment', f'{TAG} Attach', self._attach_name)
        self.check_body('attachment', f'{TAG} Attach',
                        'Content-Disposition: attachment')

        self.expect('newsletter: single email',
                    len(self._for(f'{TAG} News')) == 1)
        self.check_recipients('newsletter', f'{TAG} News',
                              ['n1@example.com', 'n2@example.com'])
        self.check_body('newsletter', f'{TAG} News', 'async-email-body')

        self.check_recipients('newsletter-filter', f'{TAG} NewsFilter',
                              self._filtered_expected)
        self.expect('newsletter-filter: excluded absent',
                    'mhu1@example.com' not in self._filtered_expected,
                    f'expected={sorted(self._filtered_expected)}')

        self.expect('retry: failed attempt not sent',
                    self._retry_after_fail == ('pending', 1),
                    f'after_fail={self._retry_after_fail}')
        self.expect('retry: success after retry',
                    self._retry_final == ('sent', 1),
                    f'final={self._retry_final}')
        self.expect('retry: exactly one email (no duplicate)',
                    len(self._for(f'{TAG} Retry')) == 1,
                    f'msgs={len(self._for(f"{TAG} Retry"))}')

        self.expect('idempotency: basic not duplicated',
                    len(self._for(f'{TAG} Basic')) == 1,
                    f'msgs={len(self._for(f"{TAG} Basic"))}')
        self.expect('idempotency: queue processed once',
                    len(self._for(f'{TAG} Queue')) == 1,
                    f'msgs={len(self._for(f"{TAG} Queue"))}')

        ids = [m['message_id'] for m in self._messages if m['message_id']]
        self.expect('global: unique Message-IDs (no dup deliveries)',
                    len(ids) == len(set(ids)),
                    f'total={len(ids)} unique={len(set(ids))}')

    def report(self, elapsed):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Validation results'))
        passed = 0
        for name, ok, detail in self._results:
            mark = self.style.SUCCESS('PASS') if ok \
                else self.style.ERROR('FAIL')
            line = f'  [{mark}] {name}'
            if not ok and detail:
                line += f'  -- {detail}'
            self.stdout.write(line)
            passed += ok
        total = len(self._results)
        tagged = len([m for m in self._messages
                      if m['subject'].startswith(TAG)])
        self.stdout.write('')
        self.stdout.write(
            f'Test emails in MailHog: {tagged}  |  '
            f'total received: {len(self._messages)}  |  '
            f'Checks: {passed}/{total} passed  |  '
            f'{elapsed:.1f}s')
        if passed != total:
            self.stderr.write(self.style.ERROR(
                f'{total - passed} check(s) FAILED'))
