# Intelligems Plugins for Claude Code

A collection of Claude Code plugins for Intelligems A/B testing automation.

## Installation

### Step 1: Add the marketplace

Open a terminal and run:

```bash
claude plugin marketplace add https://github.com/Victorpay1/intelligems-plugins.git
```

### Step 2: Install the plugins you want

```bash
claude plugin install agency-digest-setup
claude plugin install test-health-check-setup
```

Or install from within Claude Code using the `/plugin` menu.

### Step 3: Restart Claude Code

After installing, **restart Claude Code** so it loads the new skills.

### Step 4: Run the setup

```
/agency-digest-setup
```

or

```
/test-health-check-setup
```

## Updating

When updates are pushed to this repository:

### Option 1: Use the `/plugin` menu (easiest)

1. Run `/plugin` in Claude Code
2. Go to **Marketplaces** tab
3. Select **intelligems-plugins**
4. Click **"Update marketplace"** to get the latest versions

Or enable **"Enable auto-update"** to automatically stay current.

### Option 2: Update individual plugins

1. Run `/plugin` in Claude Code
2. Go to **Installed** tab
3. Select the plugin you want to update
4. Choose the update option

### Troubleshooting (if updates don't work)

There's a known bug where updates may not fully refresh the cache. If you're not getting the latest version:

1. Delete the cached plugin:
   ```bash
   rm -r ~/.claude/plugins/cache/intelligems-plugins/
   ```

2. Remove from installed plugins registry:
   - Edit `~/.claude/plugins/installed_plugins.json`
   - Remove the plugin entries (e.g., `agency-digest-setup@intelligems-plugins`)

3. Restart Claude Code completely

4. Reinstall:
   ```bash
   claude plugin install agency-digest-setup
   ```

## Uninstalling

To completely remove the plugins:

1. Delete the cache:
   ```bash
   rm -rf ~/.claude/plugins/cache/intelligems-plugins/
   ```

2. Edit `~/.claude/plugins/installed_plugins.json` and remove:
   - `agency-digest-setup@intelligems-plugins`
   - `test-health-check-setup@intelligems-plugins`

3. Edit `~/.claude/settings.json` and remove from `enabledPlugins`:
   - `agency-digest-setup@intelligems-plugins`
   - `test-health-check-setup@intelligems-plugins`

4. Restart Claude Code

To also remove the marketplace:
```bash
claude plugin marketplace remove intelligems-plugins
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

---

### test-health-check-setup

Set up automated daily Slack health checks for Intelligems A/B tests. Based on [Jerica's tutorial](https://docs.intelligems.io/developer-resources/external-api/build-an-automated-test-monitoring-integration-for-slack).

**Perfect for single brands because:**
- One message per test (detailed health status)
- Alerts when tests need attention (conversion drops, low traffic)
- Clear statistical outlook for each test
- Simpler setup than agency-digest (one API key only)

**Usage:**

After installing, run:

```
/test-health-check-setup
```

The setup wizard will guide you through:
1. Slack webhook configuration
2. Your Intelligems API key
3. Optional threshold customization
4. Daily schedule preferences
5. Test message verification

---

### Which plugin should I use?

| Feature | agency-digest-setup | test-health-check-setup |
|---------|---------------------|-------------------------|
| Brands | Multiple | Single |
| Messages | One per brand | One per test |
| Focus | Daily summary | Health monitoring |
| Alerts | Lift + confidence | Conversion drops |
| Best for | Agencies | Individual merchants |

## Requirements

- Claude Code (Pro, Max, Teams, or Enterprise)
- Intelligems API key(s) for each brand
- A Slack workspace with webhook access

## Support

For Intelligems API access, contact [support](https://portal.usepylon.com/intelligems/forms/intelligems-support-request).
