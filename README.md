# Intelligems Plugins for Claude Code

A collection of Claude Code plugins for Intelligems A/B testing automation.

## Installation

In Claude Code, run:

```
/plugin marketplace add victorpaytuvi/intelligems-plugins
```

Then install the plugin you want:

```
/plugin install agency-digest-setup
```

## Available Plugins

### agency-digest-setup

Set up automated daily Slack digests for Intelligems A/B tests across multiple brands.

**Perfect for agencies because:**
- One message per brand (ready to forward to clients)
- Shows the metrics that matter (rev/visitor, profit/visitor, conversion, AOV)
- Health status at a glance (which tests need attention)
- No more logging into multiple accounts every morning

**Usage:**

After installing, run:

```
/agency-digest-setup
```

The setup wizard will guide you through:
1. Slack webhook configuration
2. Brand names and API keys
3. Daily schedule preferences
4. Test message verification

## Requirements

- Claude Code (Pro, Max, Teams, or Enterprise)
- Intelligems API key(s) for each brand
- A Slack workspace with webhook access

## Support

For Intelligems API access, contact [support](https://portal.usepylon.com/intelligems/forms/intelligems-support-request).
