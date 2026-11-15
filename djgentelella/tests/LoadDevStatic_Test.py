"""loaddevstatic against a flaky CDN: retries, no silent holes, no partial files."""

import os
from tempfile import TemporaryDirectory
from unittest import mock

import requests
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from djgentelella.management.commands import loaddevstatic as command


class Response:
    def __init__(self, content=b'console.log(1);', status=200):
        self.content = content
        self.status_code = status
        self.ok = status < 400


class FakeSession:
    """Answers by url; an exception instance is raised instead."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append((url, timeout))
        answer = self.answers[url]
        if isinstance(answer, Exception):
            raise answer
        return answer


class LoadDevStaticTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(command.NETWORK_FAILURES.clear)
        command.NETWORK_FAILURES.clear()
        self.dir = self.enterContext(TemporaryDirectory())

    def test_the_session_retries_with_backoff(self):
        adapter = command.make_session().get_adapter('https://cdn.jsdelivr.net/x')
        self.assertEqual(adapter.max_retries.total, 5)
        self.assertEqual(adapter.max_retries.backoff_factor, 1)
        self.assertIn(503, adapter.max_retries.status_forcelist)

    def test_a_network_error_does_not_kill_the_thread(self):
        session = FakeSession({
            'https://a/1.js': requests.exceptions.SSLError('EOF'),
            'https://a/2.js': Response(b'two'),
        })
        urls = [('https://a/1.js', os.path.join(self.dir, '1.js')),
                ('https://a/2.js', os.path.join(self.dir, '2.js'))]
        with mock.patch.object(command, 'make_session', return_value=session):
            command.download(urls)
        self.assertFalse(os.path.exists(urls[0][1]))
        with open(urls[1][1], 'rb') as handle:
            self.assertEqual(handle.read(), b'two')
        self.assertEqual([url for url, _ in command.NETWORK_FAILURES],
                         ['https://a/1.js'])
        self.assertEqual(session.calls[0][1], command.TIMEOUT)

    def test_a_gone_path_is_skipped_but_not_a_network_failure(self):
        session = FakeSession({'https://a/gone.js': Response(b'', 404)})
        self.assertIsNone(command.fetch(session, 'https://a/gone.js'))
        self.assertEqual(command.NETWORK_FAILURES, [])

    def test_a_list_file_is_written_whole_or_not_at_all(self):
        target = os.path.join(self.dir, 'tinymce-all.js')
        failing = FakeSession({
            'https://a/p1.js': Response(b'p1'),
            'https://a/p2.js': requests.exceptions.ConnectionError('reset'),
        })
        with mock.patch.object(command, 'make_session', return_value=failing):
            command.Command().get_static_list_file(
                ['https://a/p1.js', 'https://a/p2.js'], target)
        self.assertFalse(os.path.exists(target))

        command.NETWORK_FAILURES.clear()
        working = FakeSession({'https://a/p1.js': Response(b'p1'),
                               'https://a/p2.js': Response(b'p2')})
        with mock.patch.object(command, 'make_session', return_value=working):
            command.Command().get_static_list_file(
                ['https://a/p1.js', 'https://a/p2.js'], target)
        with open(target, 'rb') as handle:
            self.assertEqual(handle.read(), b'p1\np2\n')

    def test_network_failures_fail_the_command_at_the_end(self):
        command.Command().report_network_failures()  # nothing failed: no error
        command.NETWORK_FAILURES.append(('https://a/1.js', 'EOF'))
        with self.assertRaises(CommandError) as caught:
            command.Command().report_network_failures()
        self.assertIn('https://a/1.js', str(caught.exception))
