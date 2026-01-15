# File Templates

These are the exact files to create for the Agency Morning Digest.

---

## agency_digest.py

```python
#!/usr/bin/env python3
"""
Agency Morning Digest - Multi-Brand Test Status

Sends a consolidated Slack message with all active tests across multiple brands.
Each brand has its own Intelligems API key.
"""
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional
from config import (
    SLACK_WEBHOOK_URL,
    API_BASE,
    MIN_RUNTIME_DAYS,
    MIN_SESSIONS_FOR_SIGNIFICANCE,
    MIN_ORDERS_FOR_SIGNIFICANCE,
    MIN_CONFIDENCE_LEVEL,
    NEUTRAL_LIFT_THRESHOLD
)


class AgencyDigest:
    """Fetch and analyze Intelligems test data across multiple brands."""

    def __init__(self, brands_file: str = "brands.json"):
        self.brands = self.load_brands(brands_file)

    def clean_test_name(self, name: str) -> str:
        """Remove internal codes from test names (e.g., 'V_BOL_PDP_13 |' prefix)."""
        if " | " in name:
            parts = name.split(" | ", 1)
            if len(parts) > 1:
                return parts[1].strip()
        return name.strip()

    def load_brands(self, brands_file: str) -> List[Dict]:
        """Load brand configurations from JSON file."""
        try:
            with open(brands_file, 'r') as f:
                data = json.load(f)
                return data.get("brands", [])
        except FileNotFoundError:
            print(f"Error: {brands_file} not found. Please create it with your brand configs.")
            return []
        except json.JSONDecodeError as e:
            print(f"Error parsing {brands_file}: {e}")
            return []

    def get_active_tests(self, api_key: str) -> List[Dict]:
        """Fetch all currently running tests for a brand."""
        headers = {
            "intelligems-access-token": api_key,
            "Content-Type": "application/json"
        }
        url = f"{API_BASE}/experiences-list"
        params = {"status": "started"}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("experiencesList", [])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching active tests: {e}")
            return []

    def get_test_analytics(self, api_key: str, experience_id: str) -> Optional[Dict]:
        """Fetch analytics data for a specific test."""
        headers = {
            "intelligems-access-token": api_key,
            "Content-Type": "application/json"
        }
        url = f"{API_BASE}/analytics/resource/{experience_id}"
        params = {"view": "overview"}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching analytics for {experience_id}: {e}")
            return None

    def calculate_runtime(self, started_ts: Optional[float]) -> str:
        """Convert timestamp (ms) to human-readable runtime."""
        if not started_ts:
            return "N/A"

        try:
            start_time = datetime.fromtimestamp(started_ts / 1000)
            runtime = datetime.now() - start_time
            days = runtime.days
            hours = runtime.seconds // 3600

            if days > 0:
                return f"{days} day{'s' if days != 1 else ''}"
            else:
                return f"{hours} hour{'s' if hours != 1 else ''}"
        except (ValueError, OSError):
            return "N/A"

    def get_metric_value(self, metrics: List[Dict], metric_name: str, variation_id: str) -> Optional[float]:
        """Extract a specific metric value for a variation."""
        for metric in metrics:
            if metric.get("variation_id") == variation_id:
                metric_data = metric.get(metric_name, {})
                if isinstance(metric_data, dict):
                    return metric_data.get("value")
        return None

    def get_metric_confidence(self, metrics: List[Dict], metric_name: str, variation_id: str) -> Optional[float]:
        """Extract confidence level (p2bb - probability to beat baseline) for a metric."""
        for metric in metrics:
            if metric.get("variation_id") == variation_id:
                metric_data = metric.get(metric_name, {})
                if isinstance(metric_data, dict):
                    return metric_data.get("p2bb")
        return None

    def calculate_runtime_days(self, started_ts: Optional[float]) -> int:
        """Calculate how many days the test has been running."""
        if not started_ts:
            return 0
        try:
            start_time = datetime.fromtimestamp(started_ts / 1000)
            runtime = datetime.now() - start_time
            return runtime.days
        except (ValueError, OSError):
            return 0

    def calculate_health_status(self, test: Dict, analytics: Optional[Dict]) -> Dict:
        """Determine test health status using 3-dimension logic."""
        if not analytics:
            return {
                "direction_emoji": "📊",
                "recommendation": "No analytics data available yet.",
                "key_metric": None,
                "lift": None,
                "lift_raw": None,
                "confidence": None,
                "total_sessions": 0
            }

        variations = analytics.get("variations", [])
        metrics = analytics.get("metrics", [])

        control = None
        variant = None
        for v in variations:
            if v.get("isControl"):
                control = v
            else:
                variant = v

        if not control or not variant:
            return {
                "direction_emoji": "📊",
                "recommendation": "Missing control or variant data.",
                "key_metric": None,
                "lift": None,
                "lift_raw": None,
                "confidence": None,
                "total_sessions": 0
            }

        control_id = control.get("id")
        variant_id = variant.get("id")

        control_sessions = self.get_metric_value(metrics, "n_visitors", control_id) or 0
        variant_sessions = self.get_metric_value(metrics, "n_visitors", variant_id) or 0
        total_sessions = control_sessions + variant_sessions

        metrics_to_show = []

        pct_cogs = self.get_metric_value(metrics, "pct_revenue_with_cogs", control_id)
        has_cogs_data = pct_cogs is not None and pct_cogs > 0

        # Revenue per visitor (the north star metric)
        rpv_control = self.get_metric_value(metrics, "net_revenue_per_visitor", control_id)
        rpv_variant = self.get_metric_value(metrics, "net_revenue_per_visitor", variant_id)
        rpv_confidence = self.get_metric_confidence(metrics, "net_revenue_per_visitor", variant_id)
        if rpv_control and rpv_variant and rpv_control != 0:
            rpv_lift = (rpv_variant - rpv_control) / rpv_control
            metrics_to_show.append({
                "name": "rev/visitor",
                "lift": rpv_lift,
                "confidence": rpv_confidence,
                "is_primary": True
            })

        # Profit per visitor (only if COGS data exists)
        if has_cogs_data:
            ppv_control = self.get_metric_value(metrics, "gross_profit_per_visitor", control_id)
            ppv_variant = self.get_metric_value(metrics, "gross_profit_per_visitor", variant_id)
            ppv_confidence = self.get_metric_confidence(metrics, "gross_profit_per_visitor", variant_id)
            if ppv_control and ppv_variant and ppv_control != 0:
                ppv_lift = (ppv_variant - ppv_control) / ppv_control
                metrics_to_show.append({
                    "name": "profit/visitor",
                    "lift": ppv_lift,
                    "confidence": ppv_confidence,
                    "is_primary": False
                })

        # Conversion rate
        conv_control = self.get_metric_value(metrics, "conversion_rate", control_id)
        conv_variant = self.get_metric_value(metrics, "conversion_rate", variant_id)
        conv_confidence = self.get_metric_confidence(metrics, "conversion_rate", variant_id)
        if conv_control and conv_variant and conv_control != 0:
            conv_lift = (conv_variant - conv_control) / conv_control
            metrics_to_show.append({
                "name": "conversion",
                "lift": conv_lift,
                "confidence": conv_confidence,
                "is_primary": False
            })

        # AOV
        aov_control = self.get_metric_value(metrics, "net_revenue_per_order", control_id)
        aov_variant = self.get_metric_value(metrics, "net_revenue_per_order", variant_id)
        aov_confidence = self.get_metric_confidence(metrics, "net_revenue_per_order", variant_id)
        if aov_control and aov_variant and aov_control != 0:
            aov_lift = (aov_variant - aov_control) / aov_control
            metrics_to_show.append({
                "name": "AOV",
                "lift": aov_lift,
                "confidence": aov_confidence,
                "is_primary": False
            })

        primary_metric = next((m for m in metrics_to_show if m["is_primary"]), None)
        if not primary_metric and metrics_to_show:
            primary_metric = metrics_to_show[0]

        lift_raw = primary_metric["lift"] if primary_metric else None
        confidence = primary_metric["confidence"] if primary_metric else None

        runtime_days = self.calculate_runtime_days(test.get("startedAtTs"))
        has_enough_time = runtime_days >= MIN_RUNTIME_DAYS
        has_enough_sessions = total_sessions >= MIN_SESSIONS_FOR_SIGNIFICANCE

        if lift_raw is not None:
            if lift_raw > NEUTRAL_LIFT_THRESHOLD:
                direction_emoji = "📈"
            elif lift_raw < -NEUTRAL_LIFT_THRESHOLD:
                direction_emoji = "📉"
            else:
                direction_emoji = "📊"
        else:
            direction_emoji = "📊"

        if not has_enough_time and not has_enough_sessions:
            recommendation = "Just getting started. Need more time and data to see the pattern."
        elif not has_enough_time and has_enough_sessions:
            recommendation = "Still early days. Let it run—good things take time to reveal themselves."
        elif has_enough_time and not has_enough_sessions:
            recommendation = "Running a while but traffic is light. Might need to check targeting."
        elif has_enough_time and has_enough_sessions:
            has_confidence = confidence is not None and confidence >= MIN_CONFIDENCE_LEVEL

            if lift_raw is None:
                recommendation = "Data available but lift couldn't be calculated."
            elif abs(lift_raw) <= NEUTRAL_LIFT_THRESHOLD:
                if has_confidence:
                    recommendation = "No meaningful difference. Sometimes that's a signal too."
                else:
                    recommendation = "Tracking flat so far. A bit more time might reveal something."
            elif lift_raw > NEUTRAL_LIFT_THRESHOLD:
                if has_confidence:
                    recommendation = "Strong signal here. Data suggests this change could capture real upside."
                else:
                    recommendation = "Looking promising. A bit more time should give us the answer."
            else:
                if has_confidence:
                    recommendation = "Now we know: this one's not the path forward. Good to have clarity."
                else:
                    recommendation = "Trending down but not conclusive. Let's see where it lands."
        else:
            recommendation = "Gathering data..."

        return {
            "direction_emoji": direction_emoji,
            "recommendation": recommendation,
            "metrics": metrics_to_show,
            "lift_raw": lift_raw,
            "confidence": f"{confidence * 100:.0f}%" if confidence else None,
            "total_visitors": int(total_sessions),
            "runtime_days": runtime_days,
            "has_cogs_data": has_cogs_data
        }

    def format_brand_message(self, brand_name: str, tests: List[Dict]) -> Dict:
        """Build a Slack message for a single brand."""
        text_lines = [f"*Hey team! Here's your {brand_name} test update:*"]
        text_lines.append("")
        text_lines.append("---")

        if not tests:
            text_lines.append("")
            text_lines.append("No active tests running.")
        else:
            strong_signals = 0

            for i, test_data in enumerate(tests, 1):
                test = test_data["test"]
                health = test_data["health"]

                raw_name = test.get("name", "Unnamed Test")
                test_name = self.clean_test_name(raw_name)
                direction_emoji = health.get("direction_emoji", "📊")
                metrics = health.get("metrics", [])
                recommendation = health.get("recommendation", "")
                total_visitors = health.get("total_visitors", 0)
                lift_raw = health.get("lift_raw")
                runtime_days = health.get("runtime_days", 0)
                has_cogs_data = health.get("has_cogs_data", True)

                primary_metric = next((m for m in metrics if m.get("is_primary")), None)
                if not primary_metric and metrics:
                    primary_metric = metrics[0]
                if primary_metric:
                    conf = primary_metric.get("confidence")
                    lift = primary_metric.get("lift")
                    if conf and lift is not None:
                        if conf >= MIN_CONFIDENCE_LEVEL and abs(lift) > NEUTRAL_LIFT_THRESHOLD:
                            strong_signals += 1

                text_lines.append("")
                text_lines.append(f"*Test {i}: {test_name}*")
                text_lines.append("")

                if metrics:
                    for metric in metrics:
                        lift_val = metric.get("lift")
                        metric_name = metric.get("name", "")
                        metric_conf = metric.get("confidence")

                        if lift_val is not None:
                            if metric_conf:
                                text_lines.append(f"• {lift_val * 100:+.1f}% {metric_name} ({metric_conf * 100:.0f}% conf)")
                            else:
                                text_lines.append(f"• {lift_val * 100:+.1f}% {metric_name}")
                else:
                    text_lines.append("• Gathering data...")

                text_lines.append(f"• {runtime_days} day{'s' if runtime_days != 1 else ''}")
                text_lines.append(f"• {total_visitors:,} visitors")

                if not has_cogs_data:
                    text_lines.append("• No profit data (no COGS)")

                if recommendation:
                    text_lines.append("")
                    text_lines.append(f"_{recommendation}_")

                text_lines.append("")
                text_lines.append("---")

            total_tests = len(tests)
            text_lines.append("")
            if strong_signals > 0:
                text_lines.append(f"*Summary:* {total_tests} test{'s' if total_tests != 1 else ''} running · {strong_signals} showing signal")
            else:
                text_lines.append(f"*Summary:* {total_tests} test{'s' if total_tests != 1 else ''} running · Still building data")

        full_text = "\n".join(text_lines)

        return {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": full_text
                    }
                }
            ]
        }

    def format_slack_message(self, all_brand_data: Dict[str, List[Dict]]) -> Dict:
        """Build consolidated Slack message."""
        today = datetime.now().strftime("%b %d")
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Test Digest - {today}",
                    "emoji": True
                }
            }
        ]

        brands_with_tests = []
        brands_without_tests = []

        for brand_name, tests in all_brand_data.items():
            if tests:
                brands_with_tests.append((brand_name, tests))
            else:
                brands_without_tests.append(brand_name)

        for brand_name, tests in brands_with_tests:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{brand_name}*"
                }
            })

            for test_data in tests:
                test = test_data["test"]
                health = test_data["health"]
                runtime = test_data["runtime"]

                raw_name = test.get("name", "Unnamed Test")
                test_name = self.clean_test_name(raw_name)
                direction_emoji = health.get("direction_emoji", "📊")
                lift = health.get("lift")
                confidence = health.get("confidence")
                recommendation = health.get("recommendation", "")
                total_visitors = health.get("total_visitors", 0)

                test_text = f"*{test_name}*\n"
                if lift and confidence:
                    test_text += f"{direction_emoji} {lift} • {confidence} confidence\n"
                elif lift:
                    test_text += f"{direction_emoji} {lift}\n"
                else:
                    test_text += f"{direction_emoji} Gathering data...\n"

                test_text += f"{runtime} • {total_visitors:,} visitors"
                if recommendation:
                    test_text += f"\n{recommendation}"

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": test_text
                    }
                })

        if brands_without_tests:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"_No active tests: {', '.join(brands_without_tests)}_"
                }
            })

        return {"blocks": blocks}

    def send_to_slack(self, message: Dict) -> bool:
        """Send message to Slack webhook."""
        if not SLACK_WEBHOOK_URL:
            print("Error: SLACK_WEBHOOK_URL not configured in .env")
            return False

        try:
            response = requests.post(
                SLACK_WEBHOOK_URL,
                json=message,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            print("Message sent to Slack successfully!")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error sending to Slack: {e}")
            return False

    def run(self, dry_run: bool = False, consolidated: bool = False):
        """Main execution: fetch all brands, compile digest, send to Slack."""
        if not self.brands:
            print("No brands configured. Please add brands to brands.json")
            return

        print(f"Processing {len(self.brands)} brand(s)...")
        all_brand_data = {}

        for brand in self.brands:
            brand_name = brand.get("display_name") or brand.get("name", "Unknown Brand")
            api_key = brand.get("api_key", "")

            if not api_key:
                print(f"  Skipping {brand_name}: no API key")
                continue

            print(f"  Fetching tests for {brand_name}...")
            tests = self.get_active_tests(api_key)
            print(f"    Found {len(tests)} active test(s)")

            brand_tests = []
            for test in tests:
                experience_id = test.get("id")
                if not experience_id:
                    continue

                analytics = self.get_test_analytics(api_key, experience_id)
                health = self.calculate_health_status(test, analytics)
                runtime = self.calculate_runtime(test.get("startedAtTs"))

                brand_tests.append({
                    "test": test,
                    "analytics": analytics,
                    "health": health,
                    "runtime": runtime
                })

            all_brand_data[brand_name] = brand_tests

        if consolidated:
            message = self.format_slack_message(all_brand_data)
            if dry_run:
                print("\n--- DRY RUN: Consolidated Message Preview ---")
                print(json.dumps(message, indent=2))
            else:
                self.send_to_slack(message)
        else:
            for brand_name, tests in all_brand_data.items():
                message = self.format_brand_message(brand_name, tests)
                if dry_run:
                    print(f"\n--- DRY RUN: {brand_name} ---")
                    print(json.dumps(message, indent=2))
                else:
                    print(f"  Sending message for {brand_name}...")
                    self.send_to_slack(message)


def main():
    import sys
    dry_run = "--dry-run" in sys.argv
    consolidated = "--consolidated" in sys.argv

    digest = AgencyDigest()
    digest.run(dry_run=dry_run, consolidated=consolidated)


if __name__ == "__main__":
    main()
```

---

## config.py

```python
"""Configuration for Agency Morning Digest."""
import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
API_BASE = "https://api.intelligems.io/v25-10-beta"

# Health Check Thresholds (aligned with Intelligems philosophy)
MIN_RUNTIME_DAYS = 10  # Don't call winners before this
MIN_SESSIONS_FOR_SIGNIFICANCE = 100
MIN_ORDERS_FOR_SIGNIFICANCE = 10
MIN_CONFIDENCE_LEVEL = 0.80  # 80% is enough ("we're not making cancer medicine")
NEUTRAL_LIFT_THRESHOLD = 0.05  # ±5% considered flat/neutral
```

---

## brands.json

Replace `{BRAND_NAME}` and `{API_KEY}` with user's values:

```json
{
  "brands": [
    {
      "name": "{BRAND_NAME}",
      "display_name": "{BRAND_NAME}",
      "api_key": "{API_KEY}"
    }
  ]
}
```

---

## .env

Replace `{WEBHOOK_URL}` with user's Slack webhook:

```
SLACK_WEBHOOK_URL={WEBHOOK_URL}
```

---

## requirements.txt

```
requests==2.31.0
python-dotenv==1.0.0
```

---

## .gitignore

```
# Credentials
.env
brands.json

# Python
__pycache__/
*.pyc
venv/
.venv/
```

---

## LaunchAgent plist (macOS scheduler)

Save to `~/Library/LaunchAgents/com.intelligems.agency-digest.plist`

Replace `{PYTHON_PATH}`, `{SCRIPT_PATH}`, and `{WORKING_DIR}` with actual paths:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.intelligems.agency-digest</string>
    <key>ProgramArguments</key>
    <array>
        <string>{PYTHON_PATH}</string>
        <string>{SCRIPT_PATH}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{WORKING_DIR}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/agency-digest.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/agency-digest.error.log</string>
</dict>
</plist>
```
