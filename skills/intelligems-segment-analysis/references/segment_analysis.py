#!/usr/bin/env python3
"""
Intelligems Segment Winner Analysis

Shows which segments each active experiment is winning in:
- Device type (desktop, mobile, tablet)
- Visitor type (new, returning)
- Traffic source (paid, organic, direct, etc.)

"Winning" = 80%+ confidence on Revenue Per Visitor
"""

import os
import sys
from datetime import datetime
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv
import requests
from tabulate import tabulate

from config import API_BASE, MIN_CONFIDENCE, MIN_RUNTIME_DAYS, SEGMENT_TYPES


class IntelligemsAPI:
    """Client for Intelligems External API."""

    def __init__(self, api_key: str):
        self.headers = {
            "intelligems-access-token": api_key,
            "Content-Type": "application/json"
        }

    def get_active_experiments(self) -> List[Dict]:
        """Fetch all currently running experiments."""
        url = f"{API_BASE}/experiences-list"
        params = {"status": "started", "category": "experiment"}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json().get("experiencesList", [])

    def get_overview_analytics(self, experiment_id: str) -> Dict:
        """Fetch overview analytics for an experiment."""
        url = f"{API_BASE}/analytics/resource/{experiment_id}"
        params = {"view": "overview"}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_segment_analytics(self, experiment_id: str, segment_type: str) -> Dict:
        """Fetch analytics segmented by audience type."""
        url = f"{API_BASE}/analytics/resource/{experiment_id}"
        params = {"view": "audience", "audience": segment_type}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()


def get_metric_value(metrics: List[Dict], metric_name: str, variation_id: str) -> Optional[float]:
    """Extract a metric value for a specific variation."""
    for metric in metrics:
        if metric.get("variation_id") == variation_id:
            metric_data = metric.get(metric_name, {})
            if isinstance(metric_data, dict):
                return metric_data.get("value")
    return None


def get_metric_uplift(metrics: List[Dict], metric_name: str, variation_id: str) -> Optional[float]:
    """Extract uplift value for a metric."""
    for metric in metrics:
        if metric.get("variation_id") == variation_id:
            metric_data = metric.get(metric_name, {})
            if isinstance(metric_data, dict):
                uplift = metric_data.get("uplift", {})
                if isinstance(uplift, dict):
                    return uplift.get("value")
    return None


def get_metric_confidence(metrics: List[Dict], metric_name: str, variation_id: str) -> Optional[float]:
    """Extract p2bb (probability to beat baseline) for a metric."""
    for metric in metrics:
        if metric.get("variation_id") == variation_id:
            metric_data = metric.get(metric_name, {})
            if isinstance(metric_data, dict):
                return metric_data.get("p2bb")
    return None


def has_cogs_data(metrics: List[Dict]) -> bool:
    """Check if COGS data exists by looking at pct_revenue_with_cogs."""
    for metric in metrics:
        pct_cogs = metric.get("pct_revenue_with_cogs", {})
        if isinstance(pct_cogs, dict):
            value = pct_cogs.get("value", 0)
            if value and value > 0:
                return True
    return False


def calculate_runtime(started_ts: Optional[float]) -> str:
    """Convert timestamp (ms) to human-readable runtime."""
    if not started_ts:
        return "N/A"
    start = datetime.fromtimestamp(started_ts / 1000)
    delta = datetime.now() - start
    return f"{delta.days} days"


def get_runtime_days(started_ts: Optional[float]) -> int:
    """Get runtime in days from timestamp (ms)."""
    if not started_ts:
        return 0
    start = datetime.fromtimestamp(started_ts / 1000)
    delta = datetime.now() - start
    return delta.days


def get_total_visitors(metrics: List[Dict]) -> int:
    """Sum visitors across all variations."""
    total = 0
    for metric in metrics:
        visitors = metric.get("n_visitors", {})
        if isinstance(visitors, dict):
            total += visitors.get("value", 0) or 0
    return int(total)


def get_total_orders(metrics: List[Dict]) -> int:
    """Sum orders across all variations."""
    total = 0
    for metric in metrics:
        orders = metric.get("n_orders", {})
        if isinstance(orders, dict):
            total += orders.get("value", 0) or 0
    return int(total)


def find_control_variation(variations: List[Dict]) -> Optional[Dict]:
    """Find the control/baseline variation."""
    for v in variations:
        if v.get("isControl"):
            return v
    return None


def determine_segment_status(
    metrics: List[Dict],
    variations: List[Dict],
    show_gpv: bool,
    is_mature: bool = True
) -> Dict[str, Any]:
    """
    Determine the status for a segment.

    Returns dict with:
    - variation: name of the variation being evaluated
    - status: "Doing well", "Not doing well", "Inconclusive", or "Too early"
    - rpv_lift: lift percentage for RPV
    - gpv_lift: lift percentage for GPV (or None)
    - confidence: p2bb as percentage
    - visitors: total visitors in this segment
    - orders: total orders in this segment
    """
    # Calculate total visitors and orders for this segment
    total_visitors = get_total_visitors(metrics)
    total_orders = get_total_orders(metrics)

    control = find_control_variation(variations)
    if not control:
        return {"variation": "-", "status": "No control", "rpv_lift": None, "gpv_lift": None, "confidence": None, "visitors": total_visitors, "orders": total_orders}

    # Find primary non-control variation (for fallback)
    primary_variant = None
    for v in variations:
        if not v.get("isControl"):
            primary_variant = v
            break

    control_id = control["id"]
    best_confidence = 0
    best_rpv_lift = None
    best_gpv_lift = None
    best_variation_name = None

    for v in variations:
        if v.get("isControl"):
            continue

        var_id = v["id"]
        rpv_conf = get_metric_confidence(metrics, "net_revenue_per_visitor", var_id)
        rpv_uplift = get_metric_uplift(metrics, "net_revenue_per_visitor", var_id)

        if rpv_conf is None:
            continue

        # Check if this variation beats baseline with 80%+ confidence
        if rpv_conf >= MIN_CONFIDENCE and rpv_uplift is not None and rpv_uplift > 0:
            if rpv_conf > best_confidence:
                best_confidence = rpv_conf
                best_rpv_lift = rpv_uplift
                best_variation_name = v["name"]

                if show_gpv:
                    best_gpv_lift = get_metric_uplift(metrics, "gross_profit_per_visitor", var_id)

    if best_rpv_lift is not None and best_confidence >= MIN_CONFIDENCE:
        return {
            "variation": best_variation_name,
            "status": "Too early" if not is_mature else "Doing well",
            "rpv_lift": best_rpv_lift,
            "gpv_lift": best_gpv_lift,
            "confidence": best_confidence,
            "visitors": total_visitors,
            "orders": total_orders
        }

    # Check if control is winning (variant is losing with 80%+ confidence)
    for v in variations:
        if v.get("isControl"):
            continue

        var_id = v["id"]
        rpv_conf = get_metric_confidence(metrics, "net_revenue_per_visitor", var_id)
        rpv_uplift = get_metric_uplift(metrics, "net_revenue_per_visitor", var_id)

        if rpv_conf is not None and rpv_uplift is not None:
            # If variant is losing with high confidence, control wins
            if (1 - rpv_conf) >= MIN_CONFIDENCE and rpv_uplift < 0:
                return {
                    "variation": v["name"],
                    "status": "Too early" if not is_mature else "Not doing well",
                    "rpv_lift": rpv_uplift,
                    "gpv_lift": get_metric_uplift(metrics, "gross_profit_per_visitor", var_id) if show_gpv else None,
                    "confidence": 1 - rpv_conf,
                    "visitors": total_visitors,
                    "orders": total_orders
                }

    # Return inconclusive with primary variant info
    primary_name = primary_variant["name"] if primary_variant else "-"
    primary_id = primary_variant["id"] if primary_variant else None

    return {
        "variation": primary_name,
        "status": "Too early" if not is_mature else "Inconclusive",
        "rpv_lift": best_rpv_lift if best_rpv_lift else (get_metric_uplift(metrics, "net_revenue_per_visitor", primary_id) if primary_id else None),
        "gpv_lift": best_gpv_lift if best_gpv_lift else (get_metric_uplift(metrics, "gross_profit_per_visitor", primary_id) if show_gpv and primary_id else None),
        "confidence": get_metric_confidence(metrics, "net_revenue_per_visitor", primary_id) if primary_id else None,
        "visitors": total_visitors,
        "orders": total_orders
    }


def format_lift(lift: Optional[float]) -> str:
    """Format lift as percentage string."""
    if lift is None:
        return "-"
    sign = "+" if lift > 0 else ""
    return f"{sign}{lift * 100:.1f}%"


def format_confidence(conf: Optional[float]) -> str:
    """Format confidence as percentage string."""
    if conf is None:
        return "Low data"
    return f"{conf * 100:.0f}%"


def print_experiment_header(experiment: Dict, overview: Dict):
    """Print experiment name and stats header."""
    name = experiment.get("name", "Unknown")
    runtime = calculate_runtime(experiment.get("startedAtTs"))

    metrics = overview.get("metrics", [])
    visitors = get_total_visitors(metrics)
    orders = get_total_orders(metrics)

    print()
    print("=" * 70)
    print(f"  {name}")
    print(f"   Runtime: {runtime} | Visitors: {visitors:,} | Orders: {orders:,}")
    print("=" * 70)


def print_segment_table(segment_label: str, segment_icon: str, rows: List[List], show_gpv: bool):
    """Print a formatted table for a segment type."""
    print()
    print(f"{segment_icon} {segment_label}")

    if show_gpv:
        headers = ["Segment", "Visitors", "Orders", "Variation", "Status", "RPV Lift", "GPV Lift", "Confidence"]
        colalign = ("left", "right", "right", "left", "left", "right", "right", "right")
    else:
        headers = ["Segment", "Visitors", "Orders", "Variation", "Status", "RPV Lift", "Confidence"]
        colalign = ("left", "right", "right", "left", "left", "right", "right")

    print(tabulate(rows, headers=headers, tablefmt="rounded_outline", colalign=colalign))


def analyze_experiment(api: IntelligemsAPI, experiment: Dict):
    """Analyze a single experiment across all segment types."""
    exp_id = experiment["id"]

    # Get overview for header stats
    overview = api.get_overview_analytics(exp_id)
    overview_metrics = overview.get("metrics", [])
    show_gpv = has_cogs_data(overview_metrics)

    # Check if test is mature enough for status judgments
    runtime_days = get_runtime_days(experiment.get("startedAtTs"))
    is_mature = runtime_days >= MIN_RUNTIME_DAYS

    print_experiment_header(experiment, overview)

    # Analyze each segment type
    segment_icons = {
        "device_type": "\U0001F4F1",      # mobile phone
        "visitor_type": "\U0001F464",     # bust in silhouette
        "source_channel": "\U0001F310",   # globe with meridians
    }

    for segment_type, segment_label in SEGMENT_TYPES:
        try:
            segment_data = api.get_segment_analytics(exp_id, segment_type)
        except requests.RequestException as e:
            print(f"\n{segment_icons.get(segment_type, '')} {segment_label}")
            print(f"   Error fetching segment data: {e}")
            continue

        metrics_by_segment = segment_data.get("metrics", [])
        variations = segment_data.get("variations", [])

        if not metrics_by_segment:
            print(f"\n{segment_icons.get(segment_type, '')} {segment_label}")
            print("   No segment data available")
            continue

        # Group metrics by segment value (API returns segment value in "audience" field)
        segments = {}
        for metric in metrics_by_segment:
            seg_value = metric.get("audience") or metric.get(segment_type) or "Unknown"
            if seg_value not in segments:
                segments[seg_value] = []
            segments[seg_value].append(metric)

        rows = []
        for seg_value, seg_metrics in segments.items():
            result = determine_segment_status(seg_metrics, variations, show_gpv, is_mature)

            if show_gpv:
                rows.append([
                    seg_value,
                    f"{result['visitors']:,}",
                    f"{result['orders']:,}",
                    result["variation"],
                    result["status"],
                    format_lift(result["rpv_lift"]),
                    format_lift(result["gpv_lift"]),
                    format_confidence(result["confidence"])
                ])
            else:
                rows.append([
                    seg_value,
                    f"{result['visitors']:,}",
                    f"{result['orders']:,}",
                    result["variation"],
                    result["status"],
                    format_lift(result["rpv_lift"]),
                    format_confidence(result["confidence"])
                ])

        icon = segment_icons.get(segment_type, "")
        print_segment_table(segment_label, icon, rows, show_gpv)


def main():
    """Main entry point."""
    load_dotenv()

    api_key = os.getenv("INTELLIGEMS_API_KEY")
    if not api_key:
        print("Error: INTELLIGEMS_API_KEY not found in environment")
        print("Create a .env file with: INTELLIGEMS_API_KEY=your_key_here")
        sys.exit(1)

    api = IntelligemsAPI(api_key)

    print("\nFetching active experiments...")

    try:
        experiments = api.get_active_experiments()
    except requests.RequestException as e:
        print(f"Error fetching experiments: {e}")
        sys.exit(1)

    if not experiments:
        print("No active experiments found.")
        sys.exit(0)

    print(f"Found {len(experiments)} active experiment(s)")

    for experiment in experiments:
        try:
            analyze_experiment(api, experiment)
        except requests.RequestException as e:
            print(f"\nError analyzing {experiment.get('name', 'Unknown')}: {e}")
            continue

    print("\n" + "=" * 70)
    print("  Analysis complete")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
