"""SLMC monitor. Python 3.11+, standard library only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from html.parser import HTMLParser
from urllib.parse import urlencode
from urllib.request import Request, urlopen

URL = 'https://slmc.gov.lk/en/services/apprentice-pharmacist'
STATE = Path(os.getenv('STATE_FILE', 'state.json'))


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def classify(html):
    parser = TextParser()
    parser.feed(html)
    text = re.sub(r'\s+', ' ', ' '.join(parser.parts)).strip().lower()
    if 'apprentice pharmacist' not in text:
        raise ValueError('Expected SLMC page not found')
    section = re.search(r'step\s*2\b(.*?)step\s*3\b', text)
    if not section:
        raise ValueError('Application section missing; inspect website layout')
    section = section.group(1)
    if re.search(r'applications? (?:currently |are |are currently )?closed|not currently open|not open', section):
        return 'closed'
    if re.search(r'applications? (?:are |are now |currently |now )?open|registration (?:is |is now )?open', section):
        return 'open'
    # A removed closure banner or new account button is not proof of opening.
    return 'changed'


def fetch():
    request = Request(URL, headers={'User-Agent': 'SLMC-Personal-Availability-Monitor/1.0', 'Cache-Control': 'no-cache'})
    with urlopen(request, timeout=30) as response:
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Unexpected response type')
        body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError('Page too large')
        return body.decode('utf-8', errors='replace')


def save(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
    temporary.replace(STATE)


def message(status):
    if status == 'open':
        return 'SLMC Apprentice Pharmacist applications appear OPEN. Check the official page and apply: ' + URL
    return 'SLMC Apprentice Pharmacist application page changed: the closed notice is absent. Opening is NOT confirmed. Please check: ' + URL


def email_send(body):
    msg = EmailMessage()
    msg['Subject'] = 'SLMC apprentice pharmacist availability alert'
    msg['From'] = os.environ['SMTP_USER']
    msg['To'] = os.environ['EMAIL_TO']
    msg.set_content(body)
    host = os.getenv('SMTP_HOST') or 'smtp.gmail.com'
    port = int(os.getenv('SMTP_PORT') or '465')
    context = ssl.create_default_context()
    if port == 465:
        client = smtplib.SMTP_SSL(host, port, timeout=30, context=context)
    else:
        client = smtplib.SMTP(host, port, timeout=30)
    with client:
        if port != 465:
            client.starttls(context=context)
        client.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
        client.send_message(msg)


def whatsapp_send(body):
    query = urlencode({'phone': os.environ['WHATSAPP_PHONE'], 'apikey': os.environ['CALLMEBOT_APIKEY'], 'text': body})
    # Never log this URL: it includes the recipient and API key.
    with urlopen('https://api.callmebot.com/whatsapp.php?' + query, timeout=30) as response:
        result = response.read(100_000).decode('utf-8', errors='replace').lower()
        if 'error' in result or not any(word in result for word in ('queued', 'sent', 'success')):
            raise ValueError('WhatsApp provider did not confirm acceptance')


def channels():
    senders = {}
    groups = [(['SMTP_USER', 'SMTP_PASSWORD', 'EMAIL_TO'], 'email', email_send),
              (['WHATSAPP_PHONE', 'CALLMEBOT_APIKEY'], 'whatsapp', whatsapp_send)]
    for keys, name, sender in groups:
        present = [bool(os.getenv(key)) for key in keys]
        if any(present) and not all(present):
            raise ValueError('Incomplete configuration for ' + name)
        if all(present):
            senders[name] = sender
    if not senders:
        raise ValueError('Configure email and/or WhatsApp secrets first')
    return senders


def advance(state, status):
    if status == 'closed':
        state.update(stable='closed', candidate=None, count=0)
        return
    if state.get('candidate') == status:
        state['count'] = state.get('count', 0) + 1
    else:
        state.update(candidate=status, count=1)
    state['count'] = min(2, state['count'])
    if state['count'] >= 2 and state.get('stable') != status:
        state['stable'] = status
        state.setdefault('pending', []).append({'status': status, 'accepted': []})


def deliver(state, senders):
    failed = False
    for event in list(state.get('pending', [])):
        for name, sender in senders.items():
            if name in event['accepted']:
                continue
            try:
                sender(message(event['status']))
                event['accepted'].append(name)
                save(state)
                print(name + ': provider accepted alert (device delivery not verified)')
            except Exception as exc:
                # Exception messages may contain credentials, URLs, or addresses.
                print(name + ': notification failed (' + type(exc).__name__ + ')', file=sys.stderr)
                failed = True
        if all(name in event['accepted'] for name in senders):
            state['pending'].remove(event)
            save(state)
    return failed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Check page without sending or saving')
    parser.add_argument('--test-alert', action='store_true', help='Send a clearly labelled setup test')
    args = parser.parse_args()
    if args.dry_run:
        print('SLMC status:', classify(fetch()))
        return 0
    senders = channels()
    if args.test_alert:
        failed = False
        for name, sender in senders.items():
            try:
                sender('TEST ONLY: your SLMC monitor is connected. This does not mean applications are open. ' + URL)
                print(name + ': test accepted')
            except Exception as exc:
                print(name + ': test failed (' + type(exc).__name__ + ')')
                failed = True
        return int(failed)
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'stable': 'closed', 'pending': []}
    failed = False
    try:
        status = classify(fetch())
        print('SLMC status:', status)
        advance(state, status)
    except Exception as exc:
        state.update(candidate=None, count=0)
        print('Check failed (' + type(exc).__name__ + '); no opening inferred', file=sys.stderr)
        failed = True
    save(state)
    return int(deliver(state, senders) or failed)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('Monitor failed (' + type(exc).__name__ + '); check configuration/state', file=sys.stderr)
        sys.exit(1)
