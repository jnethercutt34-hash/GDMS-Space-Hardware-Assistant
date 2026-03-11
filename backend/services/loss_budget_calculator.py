"""COM-informed loss budget calculator for high-speed serial links.

Provides a simplified insertion-loss budget estimator that breaks a
channel into segments (PCB trace, vias, connectors, packages) and
checks the total against spec-driven or COM-derived limits.
"""
from typing import List, Optional

from models.sipi_guide import LossBudgetSegment, LossBudgetResult


# ---------------------------------------------------------------------------
# Per-interface loss limits (dB at Nyquist frequency)
# ---------------------------------------------------------------------------

INTERFACE_LOSS_LIMITS = {
    "PCIe_Gen3": {"nyquist_ghz": 4.0,  "max_loss_db": 8.0},
    "PCIe_Gen4": {"nyquist_ghz": 8.0,  "max_loss_db": 8.0},
    "PCIe_Gen5": {"nyquist_ghz": 16.0, "max_loss_db": 8.0},
    "USB3":      {"nyquist_ghz": 2.5,  "max_loss_db": 7.0},
    "USB4":      {"nyquist_ghz": 10.0, "max_loss_db": 8.0},
    "Ethernet_10G": {"nyquist_ghz": 5.15, "max_loss_db": 15.0},
    "Ethernet_25G": {"nyquist_ghz": 13.28, "max_loss_db": 15.0},
    "LVDS":      {"nyquist_ghz": 0.5,  "max_loss_db": 6.0},
    "SpaceFibre": {"nyquist_ghz": 3.125, "max_loss_db": 10.0},
}

# ---------------------------------------------------------------------------
# Typical loss-per-segment defaults (dB per unit)
# ---------------------------------------------------------------------------

# Rough rules of thumb at various frequencies
TYPICAL_TRACE_LOSS_DB_PER_INCH = {
    # Approximate IL/inch for standard FR-4 vs low-loss at given freq
    2.5:  {"fr4": 0.12, "low_loss": 0.07},
    4.0:  {"fr4": 0.18, "low_loss": 0.10},
    5.0:  {"fr4": 0.22, "low_loss": 0.13},
    8.0:  {"fr4": 0.35, "low_loss": 0.18},
    10.0: {"fr4": 0.45, "low_loss": 0.22},
    13.0: {"fr4": 0.55, "low_loss": 0.28},
    16.0: {"fr4": 0.70, "low_loss": 0.35},
}

TYPICAL_VIA_LOSS_DB = 0.3      # per via transition (through-hole)
TYPICAL_CONNECTOR_LOSS_DB = 0.5  # per mated connector pair
TYPICAL_PACKAGE_LOSS_DB = 0.5    # BGA escape + package trace


def _nearest_freq_key(freq_ghz: float) -> float:
    """Find the nearest frequency key in the lookup table."""
    keys = sorted(TYPICAL_TRACE_LOSS_DB_PER_INCH.keys())
    return min(keys, key=lambda k: abs(k - freq_ghz))


def calculate_loss_budget(
    interface: str,
    trace_length_inches: float = 6.0,
    num_vias: int = 4,
    num_connectors: int = 0,
    include_package: bool = True,
    material: str = "fr4",
    custom_segments: Optional[List[dict]] = None,
    custom_max_loss_db: Optional[float] = None,
) -> LossBudgetResult:
    """Build a loss budget for the given interface and channel parameters.

    Parameters
    ----------
    interface : str
        Interface ID (e.g. "PCIe_Gen4")
    trace_length_inches : float
        Total PCB trace length (one direction)
    num_vias : int
        Number of via transitions (layer changes) in the path
    num_connectors : int
        Mated connector pairs in the channel
    include_package : bool
        Whether to add BGA/package loss estimate
    material : str
        "fr4" or "low_loss"
    custom_segments : list[dict] | None
        Override with explicit segments [{segment, loss_db, notes}]
    custom_max_loss_db : float | None
        Override max channel loss if interface not in our table
    """
    limits = INTERFACE_LOSS_LIMITS.get(interface, {})
    nyquist = limits.get("nyquist_ghz", 4.0)
    max_loss = custom_max_loss_db or limits.get("max_loss_db", 10.0)

    segments: List[LossBudgetSegment] = []
    recommendations: List[str] = []

    if custom_segments:
        for seg in custom_segments:
            segments.append(LossBudgetSegment(
                segment=seg.get("segment", "Custom"),
                loss_db=seg.get("loss_db", 0),
                notes=seg.get("notes", ""),
            ))
    else:
        # PCB trace loss
        freq_key = _nearest_freq_key(nyquist)
        material_key = "low_loss" if material.lower() in ("low_loss", "lowloss", "megtron", "nelco") else "fr4"
        loss_per_inch = TYPICAL_TRACE_LOSS_DB_PER_INCH[freq_key][material_key]
        trace_loss = round(trace_length_inches * loss_per_inch, 2)

        segments.append(LossBudgetSegment(
            segment="PCB Trace",
            loss_db=trace_loss,
            notes=f"{trace_length_inches}\" × {loss_per_inch} dB/in ({material_key} @ {freq_key} GHz)",
        ))

        # Via loss
        if num_vias > 0:
            via_loss = round(num_vias * TYPICAL_VIA_LOSS_DB, 2)
            segments.append(LossBudgetSegment(
                segment="Via Transitions",
                loss_db=via_loss,
                notes=f"{num_vias} vias × {TYPICAL_VIA_LOSS_DB} dB/via",
            ))

        # Connector loss
        if num_connectors > 0:
            conn_loss = round(num_connectors * TYPICAL_CONNECTOR_LOSS_DB, 2)
            segments.append(LossBudgetSegment(
                segment="Connectors",
                loss_db=conn_loss,
                notes=f"{num_connectors} mated pair(s) × {TYPICAL_CONNECTOR_LOSS_DB} dB",
            ))

        # Package loss
        if include_package:
            segments.append(LossBudgetSegment(
                segment="IC Package (TX + RX)",
                loss_db=TYPICAL_PACKAGE_LOSS_DB * 2,
                notes="TX-side + RX-side BGA escape and package trace",
            ))

    total = round(sum(s.loss_db for s in segments), 2)
    margin = round(max_loss - total, 2)
    passes = total <= max_loss

    # Generate recommendations
    if not passes:
        over = round(total - max_loss, 2)
        recommendations.append(
            f"Channel is {over} dB over budget. Consider:"
        )
        if material.lower() == "fr4" and nyquist >= 4.0:
            recommendations.append(
                "• Switch to low-loss laminate (Megtron-6, I-Tera, etc.) — "
                "can reduce trace loss by ~40-50%."
            )
        if trace_length_inches > 4:
            recommendations.append(
                f"• Shorten trace from {trace_length_inches}\" — "
                f"each inch saves ~{loss_per_inch if not custom_segments else 0.2:.2f} dB."
            )
        if num_vias > 2:
            recommendations.append(
                f"• Reduce via transitions from {num_vias} — "
                "each via saves ~0.3 dB. Use blind/buried vias."
            )
        recommendations.append(
            "• Back-drill via stubs to reduce resonance notch."
        )
    elif margin < 2.0:
        recommendations.append(
            f"Margin is tight ({margin} dB). Consider low-loss material "
            "or shorter routing as design insurance."
        )
    else:
        recommendations.append(
            f"Good margin ({margin} dB). Current channel design should pass "
            "with comfortable headroom."
        )

    return LossBudgetResult(
        interface=interface,
        nyquist_ghz=nyquist,
        max_channel_loss_db=max_loss,
        segments=segments,
        total_loss_db=total,
        margin_db=margin,
        passes=passes,
        recommendations=recommendations,
    )
