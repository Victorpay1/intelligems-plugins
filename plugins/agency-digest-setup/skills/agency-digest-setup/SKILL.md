---
name: agency-digest-setup
description: Set up automated daily Slack digests for Intelligems A/B tests across multiple brands. Use when someone wants to create the Agency Morning Digest automation, install the Intelligems Slack integration, or build a multi-brand test monitoring system. This skill handles the complete setup - just run it and answer the questions.
---

# /agency-digest-setup

Create the complete Agency Morning Digest automation in one command.

---

## What This Creates

- **Daily Slack messages** with all active A/B tests across your brands
- **Key metrics**: rev/visitor, profit/visitor, conversion, AOV
- **Health indicators**: which tests need attention
- **One message per brand**: ready to forward to clients

---

## Usage

Run the setup script:

```bash
python3 scripts/setup.py
```

The script will:
1. Ask for your Slack webhook URL (with instructions to create one)
2. Ask for each brand's name and Intelligems API key
3. Create all necessary files in the current directory
4. Install dependencies
5. Optionally set up daily 8 AM automation (macOS)
6. Send a test message to verify it works

---

## After Setup

```bash
# Send digest now
python agency_digest.py

# Preview without sending
python agency_digest.py --dry-run

# One combined message (instead of per-brand)
python agency_digest.py --consolidated
```

---

## Requirements

- **Slack webhook URL**: Create at https://api.slack.com/apps
- **Intelligems API key(s)**: Contact support@intelligems.io for access

---

## Intelligems Philosophy

The digest follows Intelligems' testing mindset:
- **Rev/visitor is the north star** (not conversion)
- **80% confidence is enough** ("we're not making cancer medicine")
- **10-day minimum runtime** before calling winners
- Every test is a learning — no "negative" framing

---

## Files Created

| File | Purpose |
|------|---------|
| `agency_digest.py` | Main script |
| `config.py` | Thresholds and settings |
| `brands.json` | Brand API keys (gitignored) |
| `.env` | Slack webhook URL (gitignored) |
| `requirements.txt` | Python dependencies |
| `.gitignore` | Protects credentials |

---

## Customization

Edit `config.py` to adjust thresholds:

| Setting | Default | Purpose |
|---------|---------|---------|
| `MIN_RUNTIME_DAYS` | 10 | Days before calling winners |
| `MIN_CONFIDENCE_LEVEL` | 0.80 | Confidence for significance |
| `MIN_SESSIONS_FOR_SIGNIFICANCE` | 100 | Minimum visitors |
| `NEUTRAL_LIFT_THRESHOLD` | 0.05 | ±5% considered flat |

---

## Adding More Brands

Edit `brands.json`:

```json
{
  "brands": [
    {"name": "Brand A", "display_name": "Brand A Store", "api_key": "ig_live_xxx"},
    {"name": "Brand B", "display_name": "Brand B Store", "api_key": "ig_live_yyy"}
  ]
}
```

---

## Troubleshooting

**No messages received:**
- Check `/tmp/agency-digest.log` for errors
- Verify webhook URL in `.env`
- Run `python agency_digest.py --dry-run` to preview

**Scheduler not running (macOS):**
```bash
launchctl list | grep agency-digest
```

**API errors:**
- Verify API key format: `ig_live_xxxxxxxxxx`
- Contact Intelligems support for access
