import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import monitor


def page(body):
    return '<h1>Apprentice Pharmacist</h1><h3>Step 2 — Create Your e-Services Account</h3>' + body + '<h3>Step 3 — Complete the Online Application</h3>'


class MonitorTests(unittest.TestCase):
    def test_closed(self):
        self.assertEqual(monitor.classify(page('Applications Currently Closed')), 'closed')

    def test_open(self):
        self.assertEqual(monitor.classify(page('Applications are now open')), 'open')

    def test_removed_banner_is_not_open(self):
        self.assertEqual(monitor.classify(page('Create account')), 'changed')

    def test_script_does_not_trigger(self):
        self.assertEqual(monitor.classify(page('<script>Applications are now open</script>Create account')), 'changed')

    def test_error_page_rejected(self):
        with self.assertRaises(ValueError):
            monitor.classify('<h1>Maintenance</h1>')

    def test_layout_change_rejected(self):
        with self.assertRaises(ValueError):
            monitor.classify('Apprentice Pharmacist temporary unavailable')

    def test_confirmation_dedup_and_reopening(self):
        state = {'stable': 'closed', 'pending': []}
        monitor.advance(state, 'open')
        self.assertEqual(state['pending'], [])
        monitor.advance(state, 'open')
        monitor.advance(state, 'open')
        self.assertEqual(len(state['pending']), 1)
        monitor.advance(state, 'closed')
        monitor.advance(state, 'open')
        monitor.advance(state, 'open')
        self.assertEqual(len(state['pending']), 2)

    def test_partial_failure_retries_only_failed_channel(self):
        state = {'pending': [{'status': 'open', 'accepted': []}]}
        calls = []
        def ok(body):
            calls.append('email')
        def fail(body):
            raise OSError('secret must not be logged')
        with tempfile.TemporaryDirectory() as directory, patch.object(monitor, 'STATE', Path(directory) / 'state.json'):
            self.assertTrue(monitor.deliver(state, {'email': ok, 'whatsapp': fail}))
            self.assertFalse(monitor.deliver(state, {'email': ok, 'whatsapp': lambda body: None}))
            self.assertEqual(calls, ['email'])
            self.assertEqual(state['pending'], [])


if __name__ == '__main__':
    unittest.main()
