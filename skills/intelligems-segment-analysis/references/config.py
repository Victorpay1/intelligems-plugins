# Intelligems Segment Analysis Configuration

# API Configuration
API_BASE = "https://api.intelligems.io/v25-10-beta"

# Thresholds (Intelligems Philosophy: 80% is enough)
MIN_CONFIDENCE = 0.80  # 80% probability to beat baseline
MIN_RUNTIME_DAYS = 14  # Don't make status judgments until test runs 2+ weeks

# Segment types to analyze
SEGMENT_TYPES = [
    ("device_type", "BY DEVICE"),
    ("visitor_type", "BY VISITOR TYPE"),
    ("source_channel", "BY TRAFFIC SOURCE"),
]
