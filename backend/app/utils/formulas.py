"""
app/utils/formulas.py
─────────────────────
Factory functions that build Formula objects for every metric.
Keeping formula definitions here means the API/service layers
never hard-code formula strings, and the frontend always gets
consistent metadata.
"""

from __future__ import annotations

from app.models.dashboard import Formula


def suppression_rate_formula(
    suppressed_devices: int,
    total_payload_devices: int,
) -> Formula:
    return Formula(
        name="Suppression Rate",
        expression="(suppressed_devices / total_payload_devices) * 100",
        numerator="suppressed_devices",
        denominator="total_payload_devices",
        numerator_value=float(suppressed_devices),
        denominator_value=float(total_payload_devices),
    )


def cr_formula(
    intersected_devices_24h: int,
    total_clicked_devices: int,
) -> Formula:
    return Formula(
        name="24-Hour Conversion Rate",
        expression="(intersected_devices_24h / total_clicked_devices) * 100",
        numerator="intersected_devices_24h",
        denominator="total_clicked_devices",
        numerator_value=float(intersected_devices_24h),
        denominator_value=float(total_clicked_devices),
    )


def suppression_intersection_formula() -> Formula:
    """Static formula for the set-intersection step (no numeric values)."""
    return Formula(
        name="Suppression Devices",
        expression="Impression Devices ∩ Previously Organic Devices",
    )
