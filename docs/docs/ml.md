# ML Intelligence

TokenLens includes ML-powered features for forecasting, anomaly detection, and behavioral profiling.

## Burn Rate Forecaster

Predicts hourly token consumption for the next 24 hours.

- **<1 day of data**: Returns "collecting data"
- **1-6 days**: Linear extrapolation
- **≥7 days**: Holt-Winters ExponentialSmoothing (or Prophet if installed)

## Anomaly Detector

Uses IsolationForest on a rolling 14-day baseline to detect unusual patterns.

**Classifications:**
- Large context loading (input/output ratio >5:1)
- Extended conversation (>30 turns)
- Usage burst (>3× average)

## Efficiency Engine

Scores sessions 0-100 based on 5 weighted factors:
- Output/Input ratio (30%)
- Cache hit rate (25%)
- Turns to completion (20%)
- Context growth slope (15%)
- Cost per output token (10%)

## Behavioral Profiler

KMeans clustering into 3 archetypes (requires 30+ days):
- Morning Sprinter (peak 6-12)
- Steady Coder (even distribution)
- Night Owl (peak after 18)

## Retraining Schedule

- Forecaster: daily
- Anomaly detector: weekly
- Behavioral profiler: weekly

Manual retrain: `tokenlens ml retrain --all`
