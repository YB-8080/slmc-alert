# SLMC application alerts — free hosting

Checks the official Apprentice Pharmacist page and sends email and personal WhatsApp alerts. No AI API or paid server required. Python 3.11+ with no extra packages. The earlier Codex chat automation has been paused; this application runs independently once you deploy it.

## Current limitation

As checked on 5 November 2026, [CallMeBot's free WhatsApp registration](https://www.callmebot.com/blog/free-api-whatsapp-messages/) says the bot is full. If you already have a key, use it; otherwise start with email and add WhatsApp when registration becomes available. This is a third-party personal messaging service, not Meta's official business API. This package cannot provide working WhatsApp delivery without a provider account/key. It does not use a paid Twilio account.

## Deploy on GitHub Actions

1. Create a **public** GitHub repository named `slmc-alert`. Standard GitHub-hosted runners are [free for public repositories](https://docs.github.com/en/billing/concepts/product-billing/github-actions). Private repositories have usage limits.
2. Upload the contents of this folder to the repository root, including the hidden `.github/workflows/monitor.yml` folder/file. Do not upload the ZIP itself. Using Git or GitHub Desktop is easiest for including hidden folders.
3. Open **Settings → Secrets and variables → Actions → New repository secret** and enter the secrets below. Keep credentials out of code, commits, and chat.
4. Open **Settings → Actions → General → Workflow permissions** and allow read/write repository permissions. The app commits a small `state.json` to remember alerts. Branch rules must allow the workflow to push to the default branch.
5. Open **Actions → SLMC availability monitor → Run workflow**, enable `test_alert`, and run. Confirm that your configured channels receive the clearly labelled test. An accepted provider request is not proof of delivery.
6. Run once more with `test_alert` off and inspect the log. It should currently show `SLMC status: closed` if the website remains unchanged.

Scheduled runs use the default branch every 10 minutes. Two consecutive matching checks confirm a change, so normal detection takes about **10–20 minutes**, plus delivery time. GitHub can delay or drop scheduled runs; this is not an instant or guaranteed notification service. Public repository schedules can be disabled after 60 days without repository activity: check Actions periodically and re-enable if needed. See [GitHub schedule behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Secrets

| Secret | Value |
| --- | --- |
| `SMTP_USER` | Your email service username; also used as sender address |
| `SMTP_PASSWORD` | Your SMTP password or provider app password |
| `EMAIL_TO` | Email address that receives alerts |
| `SMTP_HOST` | Optional; defaults to `smtp.gmail.com` |
| `SMTP_PORT` | Optional; defaults to `465` (TLS); `587` uses STARTTLS |
| `WHATSAPP_PHONE` | Your CallMeBot-authorized number, including country code, e.g. `+947XXXXXXXX` |
| `CALLMEBOT_APIKEY` | Your personal CallMeBot API key |

For Gmail, use an app password if your account supports it, not your normal login password. Other SMTP providers work too. Configure all three required email fields and/or both WhatsApp fields. Missing fields within a channel cause a visible failed run instead of silently disabling that channel. If WhatsApp is not ready, omit both WhatsApp secrets.

Follow the current [CallMeBot activation instructions](https://www.callmebot.com/blog/free-api-whatsapp-messages/) on your own phone. The provider receives your phone number and alert text. Never put these values in the public repository. After adding WhatsApp later, send a setup test; old completed events are not replayed to newly enabled channels.

## Detection and reliability

- Looks specifically between Step 2 and Step 3, ignoring scripts and styles.
- An explicit open statement generates an opening alert after two observations.
- A missing closed notice generates a **page changed, opening not confirmed** alert after two observations. This handles a new registration link without claiming certainty.
- Fetch failures, missing sections, and unexpected responses fail the job; they never count as opening. Enable GitHub Actions failure notifications in your account and inspect failures.
- Remembers alerts across runs. Each failed channel retries on the next run; an accepted email is not resent just because WhatsApp failed.
- State includes only status and channel names, not phone numbers or passwords. Do not delete `state.json` unless you want to reset deduplication.
- An interrupted run, timeout after provider acceptance, or failed state push can cause duplicate delivery. No external messaging service provides an exactly-once guarantee here.
- A pending alert describes an earlier observation; check the current official page before acting. Provider rate limits or outages may delay WhatsApp/email.

## Run on your own server later

Export the same environment variables, then run `python3 monitor.py` every 10 minutes using cron. Run only one instance at a time; keep its working directory and `state.json` persistent. Example crontab, after saving credentials securely in the server environment or a private wrapper:

```cron
3,13,23,33,43,53 * * * * cd /opt/slmc-alert && /usr/bin/python3 monitor.py >> monitor.log 2>&1
```

The script does not automatically read `.env` files. Cron does not inherit your interactive shell environment; use a private wrapper that exports credentials. Avoid running the GitHub schedule and server cron together unless you want independent alerts.

## Local checks

```sh
python -m unittest -v
python monitor.py --dry-run
python monitor.py --test-alert
```

`--dry-run` never sends messages or updates state. `--test-alert` sends to configured recipients but does not modify availability state.

This package has not been deployed to your account. Notification delivery must be tested after you configure your own secrets. The monitored website may change its HTML and require a parser update.
