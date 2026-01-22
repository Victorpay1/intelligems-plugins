# Intelligems Segment Analysis - Setup Guide

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Intelligems API key

## Getting Your API Key

The Intelligems External API is in beta. To get access:

1. Contact Intelligems support: support@intelligems.io
2. Request API access for your account
3. They'll provide your `intelligems-access-token`

## Quick Start

### 1. Create Project Directory

```bash
mkdir intelligems-segment-analysis
cd intelligems-segment-analysis
```

### 2. Create Virtual Environment (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install requests python-dotenv tabulate
```

### 4. Create Configuration Files

Create `config.py`:
```python
# Intelligems Segment Analysis Configuration

API_BASE = "https://api.intelligems.io/v25-10-beta"
MIN_CONFIDENCE = 0.80
MIN_RUNTIME_DAYS = 14

SEGMENT_TYPES = [
    ("device_type", "BY DEVICE"),
    ("visitor_type", "BY VISITOR TYPE"),
    ("source_channel", "BY TRAFFIC SOURCE"),
]
```

Create `.env`:
```
INTELLIGEMS_API_KEY=your_api_key_here
```

### 5. Copy the Analysis Script

Copy `segment_analysis.py` to your project directory.

### 6. Run

```bash
python segment_analysis.py
```

## Understanding the Output

### Status Values

| Status | Meaning |
|--------|---------|
| Doing well | Variant beating control with 80%+ confidence |
| Not doing well | Control beating variant with 80%+ confidence |
| Inconclusive | Not enough statistical confidence |
| Too early | Test running < 2 weeks |
| Low data | Insufficient orders to calculate confidence |

### Metrics

- **Visitors** - Number of visitors in this segment
- **Orders** - Number of orders in this segment
- **Variation** - Which variation the status refers to
- **RPV Lift** - Revenue Per Visitor lift vs control
- **GPV Lift** - Gross Profit Per Visitor lift (only if COGS data exists)
- **Confidence** - Probability to beat baseline (p2bb)

## Customization

### Change Confidence Threshold

Edit `config.py`:
```python
MIN_CONFIDENCE = 0.90  # Require 90% confidence
```

### Change Minimum Runtime

Edit `config.py`:
```python
MIN_RUNTIME_DAYS = 7  # Allow judgments after 1 week
```

### Add More Segments

Available segment types:
- `device_type` - Desktop, Mobile, Tablet
- `visitor_type` - New, Returning
- `source_channel` - Paid Search, Paid Social, Direct, Organic, etc.
- `country_code` - US, CA, GB, etc.
- `landing_page_full_path` - Landing page URLs

Add to `SEGMENT_TYPES` in `config.py`:
```python
SEGMENT_TYPES = [
    ("device_type", "BY DEVICE"),
    ("visitor_type", "BY VISITOR TYPE"),
    ("source_channel", "BY TRAFFIC SOURCE"),
    ("country_code", "BY COUNTRY"),
]
```

## Troubleshooting

### "INTELLIGEMS_API_KEY not found"

Make sure your `.env` file:
1. Is in the same directory as the script
2. Contains `INTELLIGEMS_API_KEY=your_actual_key`
3. Has no extra spaces around the `=`

### "No active experiments found"

- Check your Intelligems dashboard for experiments with status "started"
- Ensure your API key has access to the correct organization

### "401 Unauthorized"

- Your API key may be invalid or expired
- Contact Intelligems support to verify your key

### Timeout or connection errors

- Check your internet connection
- The API base URL may have changed (currently v25-10-beta)
