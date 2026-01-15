#!/usr/bin/env python3
"""
Agency Digest Setup Script

Interactive setup that creates all necessary files for the Agency Morning Digest.
Run this script, answer the questions, and you're ready to go.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def get_input(prompt: str, required: bool = True) -> str:
    """Get user input with optional requirement."""
    while True:
        value = input(prompt).strip()
        if value or not required:
            return value
        print("This field is required. Please enter a value.")


def create_agency_digest_py(path: Path):
    """Create the main agency_digest.py script."""
    content = '''#!/usr/bin/env python3
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
        text_lines = [f"👋 *Hey team! Here's your {brand_name} test update:*"]
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
                text_lines.append(f"🧪 *Test {i}: {test_name}*")
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
                    text_lines.append(f"💡 _{recommendation}_")

                text_lines.append("")
                text_lines.append("---")

            total_tests = len(tests)
            text_lines.append("")
            if strong_signals > 0:
                text_lines.append(f"📊 *Summary:* {total_tests} test{'s' if total_tests != 1 else ''} running · {strong_signals} showing signal 🚀")
            else:
                text_lines.append(f"📊 *Summary:* {total_tests} test{'s' if total_tests != 1 else ''} running · Still building data")

        full_text = "\\n".join(text_lines)

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

                test_text = f"*{test_name}*\\n"
                if lift and confidence:
                    test_text += f"{direction_emoji} {lift} • {confidence} confidence\\n"
                elif lift:
                    test_text += f"{direction_emoji} {lift}\\n"
                else:
                    test_text += f"{direction_emoji} Gathering data...\\n"

                test_text += f"{runtime} • {total_visitors:,} visitors"
                if recommendation:
                    test_text += f"\\n{recommendation}"

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
                print("\\n--- DRY RUN: Consolidated Message Preview ---")
                print(json.dumps(message, indent=2))
            else:
                self.send_to_slack(message)
        else:
            for brand_name, tests in all_brand_data.items():
                message = self.format_brand_message(brand_name, tests)
                if dry_run:
                    print(f"\\n--- DRY RUN: {brand_name} ---")
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
'''
    (path / "agency_digest.py").write_text(content)
    print("  ✅ Created agency_digest.py")


def create_config_py(path: Path):
    """Create the config.py file."""
    content = '''"""Configuration for Agency Morning Digest."""
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
'''
    (path / "config.py").write_text(content)
    print("  ✅ Created config.py")


def create_requirements_txt(path: Path):
    """Create the requirements.txt file."""
    content = '''requests==2.31.0
python-dotenv==1.0.0
'''
    (path / "requirements.txt").write_text(content)
    print("  ✅ Created requirements.txt")


def create_brands_json(path: Path, brands: list):
    """Create the brands.json file with user's brands."""
    content = {"brands": brands}
    with open(path / "brands.json", 'w') as f:
        json.dump(content, f, indent=2)
    print("  ✅ Created brands.json")


def create_env_file(path: Path, webhook_url: str):
    """Create the .env file with Slack webhook."""
    content = f"SLACK_WEBHOOK_URL={webhook_url}\n"
    (path / ".env").write_text(content)
    print("  ✅ Created .env")


def create_gitignore(path: Path):
    """Create .gitignore to protect sensitive files."""
    content = '''# Credentials
.env
brands.json

# Python
__pycache__/
*.pyc
venv/
.venv/
'''
    (path / ".gitignore").write_text(content)
    print("  ✅ Created .gitignore")


def install_dependencies(path: Path):
    """Install Python dependencies."""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=path,
            check=True,
            capture_output=True
        )
        print("  ✅ Dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️ Failed to install dependencies: {e}")
        print("  Run manually: pip install -r requirements.txt")
        return False


def setup_scheduler_macos(path: Path):
    """Set up LaunchAgent for daily 8 AM execution on macOS."""
    print("\n⏰ Setting up daily scheduler...")

    plist_name = "com.intelligems.agency-digest.plist"
    plist_path = Path.home() / "Library" / "LaunchAgents" / plist_name

    # Detect Python path
    python_path = sys.executable
    script_path = path / "agency_digest.py"

    plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.intelligems.agency-digest</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{script_path}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{path}</string>
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
'''

    # Create LaunchAgents directory if needed
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    # Write plist
    plist_path.write_text(plist_content)
    print(f"  ✅ Created {plist_path}")

    # Load the agent
    try:
        subprocess.run(["launchctl", "load", str(plist_path)], check=True, capture_output=True)
        print("  ✅ Scheduler activated (runs daily at 8:00 AM)")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️ Failed to load scheduler: {e}")
        print(f"  Run manually: launchctl load {plist_path}")
        return False


def main():
    """Interactive setup for Agency Morning Digest."""
    print("=" * 60)
    print("🚀 Agency Morning Digest Setup")
    print("=" * 60)
    print()
    print("This will create everything you need to get daily Slack")
    print("updates about your Intelligems A/B tests.")
    print()

    # Get project directory
    default_dir = Path.cwd()
    print(f"📁 Project directory: {default_dir}")
    custom_dir = input("   Press Enter to use this, or type a different path: ").strip()
    project_path = Path(custom_dir) if custom_dir else default_dir
    project_path.mkdir(parents=True, exist_ok=True)

    print()
    print("-" * 60)
    print("STEP 1: Slack Webhook URL")
    print("-" * 60)
    print()
    print("You need a Slack webhook URL to send messages.")
    print()
    print("If you don't have one:")
    print("  1. Go to https://api.slack.com/apps")
    print("  2. Create New App > From scratch")
    print("  3. Enable Incoming Webhooks")
    print("  4. Add New Webhook to Workspace")
    print("  5. Copy the webhook URL")
    print()

    webhook_url = get_input("Paste your Slack webhook URL: ")

    print()
    print("-" * 60)
    print("STEP 2: Brand Configuration")
    print("-" * 60)
    print()
    print("Add the brands you want to track. You can add multiple.")
    print("(Contact Intelligems support for API keys)")
    print()

    brands = []
    while True:
        print(f"\n--- Brand {len(brands) + 1} ---")
        brand_name = get_input("Brand name (what shows in Slack): ")
        api_key = get_input("Intelligems API key: ")

        brands.append({
            "name": brand_name,
            "display_name": brand_name,
            "api_key": api_key
        })

        another = input("\nAdd another brand? (y/N): ").strip().lower()
        if another != 'y':
            break

    print()
    print("-" * 60)
    print("STEP 3: Creating Files")
    print("-" * 60)
    print()

    create_agency_digest_py(project_path)
    create_config_py(project_path)
    create_requirements_txt(project_path)
    create_brands_json(project_path, brands)
    create_env_file(project_path, webhook_url)
    create_gitignore(project_path)

    # Install dependencies
    install_dependencies(project_path)

    # Scheduler setup (macOS only)
    print()
    print("-" * 60)
    print("STEP 4: Daily Automation (Optional)")
    print("-" * 60)
    print()

    if sys.platform == "darwin":
        setup_auto = input("Set up daily 8 AM Slack messages? (Y/n): ").strip().lower()
        if setup_auto != 'n':
            setup_scheduler_macos(project_path)
    else:
        print("⚠️ Automatic scheduling is only supported on macOS.")
        print("   For Windows: Use Task Scheduler")
        print("   For Linux: Use cron")

    # Test run
    print()
    print("-" * 60)
    print("STEP 5: Test Run")
    print("-" * 60)
    print()

    test_now = input("Send a test message to Slack now? (Y/n): ").strip().lower()
    if test_now != 'n':
        print("\nRunning test...")
        subprocess.run([sys.executable, "agency_digest.py"], cwd=project_path)

    # Done
    print()
    print("=" * 60)
    print("✅ Setup Complete!")
    print("=" * 60)
    print()
    print(f"Your files are in: {project_path}")
    print()
    print("Commands:")
    print(f"  cd {project_path}")
    print("  python agency_digest.py          # Send digest now")
    print("  python agency_digest.py --dry-run # Preview without sending")
    print()
    print("To add more brands, edit brands.json")
    print()


if __name__ == "__main__":
    main()
