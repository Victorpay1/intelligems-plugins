# Intelligems Plugins for Claude Code

A collection of Claude Code plugins for Intelligems A/B testing automation.

## Installation

In Claude Code, run:

```
/plugin marketplace add https://github.com/Victorpay1/intelligems-plugins.git
```

Then install the plugin you want:

```
/plugin install agency-digest-setup
```

## Updating

When updates are pushed to this repository:

**Option 1: Try the update command**
```
/plugin update agency-digest-setup
```

**Option 2: Manual reinstall (if update doesn't work)**

There's a known bug where `/plugin update` may not fully refresh the cache. If you're not getting the latest version:

1. Delete the cached plugin:
   ```bash
   rm -r ~/.claude/plugins/cache/intelligems-plugins/
   ```

2. Remove from installed plugins registry:
   - Edit `~/.claude/plugins/installed_plugins.json`
   - Remove the `agency-digest-setup@intelligems-plugins` entry

3. Restart Claude Code completely

4. Reinstall:
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
