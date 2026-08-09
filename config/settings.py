"""Centralized runtime settings for War Room components."""

from __future__ import annotations

import os

# Data Source Feature Toggles
ENABLE_SLEEPER_ADP: bool = os.getenv("ENABLE_SLEEPER_ADP", "true").lower() in ("true", "1", "yes")
ENABLE_FANTASYPROS_ECR: bool = os.getenv("ENABLE_FANTASYPROS_ECR", "true").lower() in ("true", "1", "yes")
ENABLE_HIGH_STAKES_ADP: bool = os.getenv("ENABLE_HIGH_STAKES_ADP", "true").lower() in ("true", "1", "yes")
ENABLE_VEGAS_PROPS: bool = os.getenv("ENABLE_VEGAS_PROPS", "true").lower() in ("true", "1", "yes")
ENABLE_HIGH_STAKES_PROJECTIONS: bool = os.getenv("ENABLE_HIGH_STAKES_PROJECTIONS", "true").lower() in ("true", "1", "yes")
ENABLE_ADVANCED_METRICS: bool = os.getenv("ENABLE_ADVANCED_METRICS", "true").lower() in ("true", "1", "yes")

# Ingestion & Projection Blending Weights
WEIGHT_CONSENSUS: float = float(os.getenv("WEIGHT_CONSENSUS", "0.25"))
WEIGHT_VEGAS: float = float(os.getenv("WEIGHT_VEGAS", "0.35"))
WEIGHT_HIGH_STAKES: float = float(os.getenv("WEIGHT_HIGH_STAKES", "0.40"))


def update_data_source_settings(
    enable_sleeper_adp: bool = True,
    enable_fantasypros_ecr: bool = True,
    enable_high_stakes_adp: bool = True,
    enable_vegas_props: bool = True,
    enable_high_stakes_projections: bool = True,
    enable_advanced_metrics: bool = True,
) -> Dict[str, bool]:
    """Dynamically update data source ingestion toggles."""
    global ENABLE_SLEEPER_ADP, ENABLE_FANTASYPROS_ECR, ENABLE_HIGH_STAKES_ADP, ENABLE_VEGAS_PROPS, ENABLE_HIGH_STAKES_PROJECTIONS, ENABLE_ADVANCED_METRICS
    ENABLE_SLEEPER_ADP = bool(enable_sleeper_adp)
    ENABLE_FANTASYPROS_ECR = bool(enable_fantasypros_ecr)
    ENABLE_HIGH_STAKES_ADP = bool(enable_high_stakes_adp)
    ENABLE_VEGAS_PROPS = bool(enable_vegas_props)
    ENABLE_HIGH_STAKES_PROJECTIONS = bool(enable_high_stakes_projections)
    ENABLE_ADVANCED_METRICS = bool(enable_advanced_metrics)

    return get_active_data_sources()


def get_active_data_sources() -> Dict[str, bool]:
    """Return map of data source key -> active boolean state."""
    return {
        "espn": True,
        "sleeper": ENABLE_SLEEPER_ADP,
        "fantasypros": ENABLE_FANTASYPROS_ECR,
        "underdog_adp": ENABLE_HIGH_STAKES_ADP,
        "vegas_props": ENABLE_VEGAS_PROPS,
        "high_stakes": ENABLE_HIGH_STAKES_PROJECTIONS,
        "advanced_metrics": ENABLE_ADVANCED_METRICS,
    }
