# File Templates

These are the exact files to create for the Intelligems Test Health Check.

Based on [Jerica's tutorial](https://docs.intelligems.io/developer-resources/external-api/build-an-automated-test-monitoring-integration-for-slack).

---

## intelligems_health_check.py

```python
#!/usr/bin/env python3
"""
Intelligems Test Health Check

Monitors your A/B tests and sends daily Slack notifications with health status.
Alerts you when tests need attention (conversion drops, low traffic, etc.).
"""
import os
import requests
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Configuration
INTELLIGEMS_API_KEY = os.getenv('INTELLIGEMS_API_KEY')
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
API_BASE = "https://api.intelligems.io/v25-10-beta"

# Import thresholds from config
from config import (
    MIN_SESSIONS_FOR_SIGNIFICANCE,
    MIN_ORDERS_FOR_SIGNIFICANCE,
    CONVERSION_DROP_ALERT_THRESHOLD,
    MIN_CONFIDENCE_LEVEL
)


class IntelligemsHealthCheck:
    """Fetch and analyze Intelligems test data."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "intelligems-access-token": api_key,
            "Content-Type": "application/json"
        }

    def get_active_tests(self) -> List[Dict]:
        """Fetch all currently running tests."""
        url = f"{API_BASE}/experiences-list"
        params = {"status": "started"}

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("experiencesList", [])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching active tests: {e}")
            return []

    def get_test_analytics(self, experience_id: str) -> Optional[Dict]:
        """Fetch analytics data for a specific test."""
        url = f"{API_BASE}/analytics/resource/{experience_id}"
        params = {"view": "overview"}

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching analytics for {experience_id}: {e}")
            return None

    def calculate_runtime(self, started_ts: Optional[float]) -> tuple:
        """Convert timestamp (ms) to runtime days and hours."""
        if not started_ts:
            return 0, 0, "N/A"

        try:
            start_time = datetime.fromtimestamp(started_ts / 1000)
            runtime = datetime.now() - start_time
            days = runtime.days
            hours = runtime.seconds // 3600

            if days > 0:
                runtime_str = f"{days} day{'s' if days != 1 else ''}, {hours} hour{'s' if hours != 1 else ''}"
            else:
                runtime_str = f"{hours} hour{'s' if hours != 1 else ''}"

            return days, hours, runtime_str
        except (ValueError, OSError):
            return 0, 0, "N/A"

    def get_metric_value(self, metrics: List[Dict], metric_name: str, variation_id: str) -> Optional[float]:
        """Extract a specific metric value for a variation."""
        for metric in metrics:
            if metric.get("variation_id") == variation_id:
                metric_data = metric.get(metric_name, {})
                if isinstance(metric_data, dict):
                    return metric_data.get("value")
        return None

    def analyze_test(self, test: Dict, analytics: Optional[Dict]) -> Dict:
        """Analyze test health and determine status."""
        result = {
            "test_name": test.get("name", "Unnamed Test"),
            "has_issues": False,
            "issues": [],
            "metrics": {},
            "total_sessions": 0,
            "control_sessions": 0,
            "control_orders": 0,
            "variant_sessions": 0,
            "variant_orders": 0,
            "runtime_str": "N/A",
            "runtime_days": 0,
            "statistical_outlook": ""
        }

        if not analytics:
            result["has_issues"] = True
            result["issues"].append("No analytics data available")
            return result

        variations = analytics.get("variations", [])
        metrics = analytics.get("metrics", [])

        # Find control and variant
        control = None
        variant = None
        for v in variations:
            if v.get("isControl"):
                control = v
            else:
                variant = v

        if not control or not variant:
            result["has_issues"] = True
            result["issues"].append("Missing control or variant data")
            return result

        control_id = control.get("id")
        variant_id = variant.get("id")

        # Get sessions and orders
        control_sessions = self.get_metric_value(metrics, "n_visitors", control_id) or 0
        variant_sessions = self.get_metric_value(metrics, "n_visitors", variant_id) or 0
        control_orders = self.get_metric_value(metrics, "n_orders", control_id) or 0
        variant_orders = self.get_metric_value(metrics, "n_orders", variant_id) or 0

        result["total_sessions"] = int(control_sessions + variant_sessions)
        result["control_sessions"] = int(control_sessions)
        result["control_orders"] = int(control_orders)
        result["variant_sessions"] = int(variant_sessions)
        result["variant_orders"] = int(variant_orders)

        # Get runtime
        days, hours, runtime_str = self.calculate_runtime(test.get("startedAtTs"))
        result["runtime_str"] = runtime_str
        result["runtime_days"] = days

        # Get key metrics
        # Conversion Rate
        conv_control = self.get_metric_value(metrics, "conversion_rate", control_id)
        conv_variant = self.get_metric_value(metrics, "conversion_rate", variant_id)
        if conv_control is not None and conv_variant is not None:
            conv_lift = ((conv_variant - conv_control) / conv_control * 100) if conv_control > 0 else 0
            result["metrics"]["conversion_rate"] = {
                "control": conv_control * 100,  # Convert to percentage
                "variant": conv_variant * 100,
                "lift": conv_lift
            }

        # Revenue per Session
        rpv_control = self.get_metric_value(metrics, "net_revenue_per_visitor", control_id)
        rpv_variant = self.get_metric_value(metrics, "net_revenue_per_visitor", variant_id)
        if rpv_control is not None and rpv_variant is not None:
            rpv_lift = ((rpv_variant - rpv_control) / rpv_control * 100) if rpv_control > 0 else 0
            result["metrics"]["revenue_per_session"] = {
                "control": rpv_control,
                "variant": rpv_variant,
                "lift": rpv_lift
            }

        # AOV
        aov_control = self.get_metric_value(metrics, "net_revenue_per_order", control_id)
        aov_variant = self.get_metric_value(metrics, "net_revenue_per_order", variant_id)
        if aov_control is not None and aov_variant is not None:
            aov_lift = ((aov_variant - aov_control) / aov_control * 100) if aov_control > 0 else 0
            result["metrics"]["aov"] = {
                "control": aov_control,
                "variant": aov_variant,
                "lift": aov_lift
            }

        # Check for issues
        total_orders = control_orders + variant_orders

        # Low traffic warning
        if result["total_sessions"] < MIN_SESSIONS_FOR_SIGNIFICANCE:
            result["issues"].append(f"Low traffic: {result['total_sessions']:,} sessions (need {MIN_SESSIONS_FOR_SIGNIFICANCE:,})")

        # Low orders warning
        if total_orders < MIN_ORDERS_FOR_SIGNIFICANCE:
            result["issues"].append(f"Low orders: {int(total_orders):,} orders (need {MIN_ORDERS_FOR_SIGNIFICANCE:,})")

        # Conversion drop alert
        if "conversion_rate" in result["metrics"]:
            conv_lift = result["metrics"]["conversion_rate"]["lift"]
            if conv_lift < -(CONVERSION_DROP_ALERT_THRESHOLD * 100):
                result["has_issues"] = True
                result["issues"].append(f"Conversion dropped {abs(conv_lift):.1f}%")

        if result["issues"]:
            result["has_issues"] = True

        # Build statistical outlook
        result["statistical_outlook"] = self._build_outlook(result, total_orders)

        return result

    def _build_outlook(self, result: Dict, total_orders: int) -> str:
        """Build the statistical outlook message."""
        sessions = result["total_sessions"]

        if sessions < MIN_SESSIONS_FOR_SIGNIFICANCE:
            return f"These results are not yet statistically significant. With {result['control_orders']:,} orders to the control and {result['variant_orders']:,} to the variant, we're seeing promising early momentum. Small sample sizes can show dramatic differences — {result['variant_orders']:,} to {result['control_orders']:,} could easily reverse with more data."

        if total_orders < MIN_ORDERS_FOR_SIGNIFICANCE:
            return f"With {int(total_orders):,} total orders, we need more conversions before drawing conclusions. The test is collecting data but hasn't reached statistical significance yet."

        if result["has_issues"]:
            return "Guardian will continue monitoring for critical issues. If we see concerning patterns (like conversion rates dropping significantly), we'll alert you immediately."

        return "Your test is running smoothly. Guardian checked for issues and everything looks good."


class SlackNotifier:
    """Send formatted messages to Slack."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_health_check(self, test_results: List[Dict]) -> bool:
        """Send health check message for each test."""
        if not test_results:
            print("No active tests to report.")
            return True

        success = True
        for result in test_results:
            message = self._format_message(result)
            if not self._send(message):
                success = False

        return success

    def _format_message(self, result: Dict) -> Dict:
        """Format a single test result as a Slack message."""
        # Determine status icon
        if result["has_issues"]:
            status_icon = ":warning:"
            status_text = "TEST HEALTH CHECK"
        else:
            status_icon = ":white_check_mark:"
            status_text = "TEST HEALTH CHECK"

        # Build message blocks
        blocks = []

        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{status_icon} {status_text}",
                "emoji": True
            }
        })

        # Test name
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":call_me_hand: *{result['test_name']}*"
            }
        })

        # Status message
        if result["has_issues"]:
            status_msg = "Guardian detected some items that need your attention."
        else:
            status_msg = "Your test is running smoothly. Guardian checked for issues and everything looks good."

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": status_msg
            }
        })

        # Runtime and Sessions
        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f":calendar: *Runtime*\n{result['runtime_str']}"
                },
                {
                    "type": "mrkdwn",
                    "text": f":busts_in_silhouette: *Total Sessions*\n{result['total_sessions']:,}"
                }
            ]
        })

        # Control vs Variant
        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f":bar_chart: *Control Group*\n{result['control_sessions']:,} sessions, {result['control_orders']:,} orders"
                },
                {
                    "type": "mrkdwn",
                    "text": f":bar_chart: *New Group 1*\n{result['variant_sessions']:,} sessions, {result['variant_orders']:,} orders"
                }
            ]
        })

        # Key Metrics
        metrics_text = ":chart_with_upwards_trend: *Key Metrics*\n"

        if "conversion_rate" in result["metrics"]:
            m = result["metrics"]["conversion_rate"]
            sign = "+" if m["lift"] >= 0 else ""
            metrics_text += f"*Conversion Rate:* {m['control']:.2f}% → {m['variant']:.2f}% ({sign}{m['lift']:.1f}%)\n"

        if "revenue_per_session" in result["metrics"]:
            m = result["metrics"]["revenue_per_session"]
            sign = "+" if m["lift"] >= 0 else ""
            metrics_text += f"*Revenue/Session:* ${m['control']:.2f} → ${m['variant']:.2f} ({sign}{m['lift']:.1f}%)\n"

        if "aov" in result["metrics"]:
            m = result["metrics"]["aov"]
            sign = "+" if m["lift"] >= 0 else ""
            metrics_text += f"*AOV:* ${m['control']:.2f} → ${m['variant']:.2f} ({sign}{m['lift']:.1f}%)"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": metrics_text
            }
        })

        # Statistical Outlook
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":bar_chart: *Statistical Outlook*\n{result['statistical_outlook']}"
            }
        })

        # Issues (if any)
        if result["issues"]:
            issues_text = ":rotating_light: *Attention Needed*\n"
            for issue in result["issues"]:
                issues_text += f"• {issue}\n"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": issues_text
                }
            })

        return {"blocks": blocks}

    def _send(self, message: Dict) -> bool:
        """Send message to Slack webhook."""
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            print(f"Message sent to Slack successfully!")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error sending to Slack: {e}")
            return False


def main():
    """Main execution."""
    if not INTELLIGEMS_API_KEY:
        print("Error: INTELLIGEMS_API_KEY not set in .env")
        return

    if not SLACK_WEBHOOK_URL:
        print("Error: SLACK_WEBHOOK_URL not set in .env")
        return

    print("Fetching active tests...")
    checker = IntelligemsHealthCheck(INTELLIGEMS_API_KEY)
    tests = checker.get_active_tests()

    if not tests:
        print("No active tests found.")
        return

    print(f"Found {len(tests)} active test(s). Analyzing...")

    results = []
    for test in tests:
        experience_id = test.get("id")
        if not experience_id:
            continue

        analytics = checker.get_test_analytics(experience_id)
        result = checker.analyze_test(test, analytics)
        results.append(result)
        print(f"  - {result['test_name']}: {'Issues detected' if result['has_issues'] else 'Healthy'}")

    print("\nSending to Slack...")
    notifier = SlackNotifier(SLACK_WEBHOOK_URL)
    notifier.send_health_check(results)


if __name__ == "__main__":
    main()
```

---

## config.py

Replace values with user's preferences:

```python
"""Configuration for Intelligems Test Health Check."""

# Minimum data thresholds before analyzing
MIN_SESSIONS_FOR_SIGNIFICANCE = {MIN_SESSIONS}  # Default: 100
MIN_ORDERS_FOR_SIGNIFICANCE = {MIN_ORDERS}      # Default: 10

# Alert thresholds
CONVERSION_DROP_ALERT_THRESHOLD = {CONV_DROP}   # Default: 0.20 (20%)

# Statistical confidence
MIN_CONFIDENCE_LEVEL = {CONFIDENCE}              # Default: 0.95 (95%)
```

**Default values:**
```python
"""Configuration for Intelligems Test Health Check."""

# Minimum data thresholds before analyzing
MIN_SESSIONS_FOR_SIGNIFICANCE = 100
MIN_ORDERS_FOR_SIGNIFICANCE = 10

# Alert thresholds
CONVERSION_DROP_ALERT_THRESHOLD = 0.20  # 20%

# Statistical confidence
MIN_CONFIDENCE_LEVEL = 0.95  # 95%
```

---

## .env

Replace `{API_KEY}` and `{WEBHOOK_URL}` with user's values:

```
INTELLIGEMS_API_KEY={API_KEY}
SLACK_WEBHOOK_URL={WEBHOOK_URL}
```

---

## requirements.txt

```
requests>=2.31.0
python-dotenv>=1.0.0
```

---

## .gitignore

```
# Credentials - NEVER commit these
.env

# Python
__pycache__/
*.pyc
venv/
.venv/
```

---

## LaunchAgent plist (macOS scheduler)

Save to `~/Library/LaunchAgents/com.intelligems.health-check.plist`

Replace `{PROJECT_DIR}`, `{HOUR}`, and `{MINUTE}` with actual values.

**Important:** Use the venv Python, not system Python:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.intelligems.health-check</string>
    <key>ProgramArguments</key>
    <array>
        <string>{PROJECT_DIR}/venv/bin/python3</string>
        <string>{PROJECT_DIR}/intelligems_health_check.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{PROJECT_DIR}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{HOUR}</integer>
        <key>Minute</key>
        <integer>{MINUTE}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/intelligems-health-check.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/intelligems-health-check.error.log</string>
</dict>
</plist>
```

**Default time is 10:00 AM:**
- `{HOUR}` = 10
- `{MINUTE}` = 0
