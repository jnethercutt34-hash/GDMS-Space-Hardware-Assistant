"""Simplified COM (Channel Operating Margin) estimation engine.

Based on IEEE 802.3 Annex 93A methodology — simplified for estimation purposes.
Results are labeled as estimates; final signoff should use HyperLynx or equivalent.
"""
import math
from typing import List

from models.com_channel import ChannelModel, COMResult


def calculate_com(channel: ChannelModel) -> COMResult:
    """Compute estimated COM for a channel model.

    This is a simplified estimation, not a full-accuracy IEEE 802.3ck simulator.
    """
    warnings: List[str] = []

    # Nyquist frequency
    if channel.modulation.value == "NRZ":
        nyquist_ghz = channel.data_rate_gbps / 2.0
    else:  # PAM4
        nyquist_ghz = channel.data_rate_gbps / 4.0

    # --- Insertion Loss (IL) ---
    total_il_db = 0.0
    for seg in channel.segments:
        length_inches = seg.length_mm / 25.4
        # Scale loss from per-inch-at-Nyquist
        seg_loss = seg.loss_db_per_inch * length_inches
        # Frequency scaling (loss ∝ sqrt(f) for skin effect + f for dielectric)
        freq_factor = math.sqrt(nyquist_ghz / 10.0) if nyquist_ghz > 0 else 1.0
        seg_loss *= max(freq_factor, 0.5)
        total_il_db += seg_loss

    # --- Insertion Loss Deviation (ILD) ---
    # Simplified: estimate based on impedance discontinuities
    impedances = [s.impedance_ohm for s in channel.segments] if channel.segments else [100.0]
    avg_z = sum(impedances) / len(impedances) if impedances else 100.0
    z_deviations = [abs(z - avg_z) for z in impedances]
    max_z_dev = max(z_deviations) if z_deviations else 0.0
    ild_penalty_db = max_z_dev / avg_z * 3.0  # rough penalty for impedance mismatch

    if max_z_dev > 10.0:
        warnings.append(
            f"Impedance variation of {max_z_dev:.1f} Ω across segments — may cause reflections."
        )

    # --- Return Loss (RL) ---
    # Estimate worst-case return loss from impedance mismatches
    rl_db = 30.0  # start optimistic
    for i in range(len(impedances) - 1):
        z1, z2 = impedances[i], impedances[i + 1]
        if z1 + z2 > 0:
            gamma = abs(z2 - z1) / (z2 + z1)
            if gamma > 0:
                rl_segment = -20 * math.log10(gamma) if gamma < 1.0 else 0.0
                rl_db = min(rl_db, rl_segment)

    if rl_db < 15.0:
        warnings.append(f"Return loss {rl_db:.1f} dB is below 15 dB threshold.")

    # --- ISI penalty ---
    # Simplified: proportional to IL beyond a threshold
    isi_threshold_db = 8.0
    isi_excess_db = max(0.0, total_il_db - isi_threshold_db)
    isi_penalty_mv = isi_excess_db * 15.0  # rough mV penalty per dB excess

    # --- Equalization benefit ---
    # CTLE
    ctle_benefit_db = min(channel.rx_params.ctle_peaking_db, total_il_db * 0.6)
    ctle_benefit_mv = ctle_benefit_db * 12.0

    # DFE
    dfe_benefit_mv = channel.rx_params.dfe_taps * channel.rx_params.dfe_tap1_mv * 0.7

    # TX de-emphasis helps with ISI at far end
    tx_deemph_benefit_mv = channel.tx_params.de_emphasis_db * 10.0

    # --- Signal amplitude ---
    signal_mv = channel.tx_params.swing_mv / 2.0  # differential half-swing

    # Apply IL attenuation
    if total_il_db > 0:
        il_linear = 10 ** (-total_il_db / 20.0)
        signal_at_rx_mv = signal_mv * il_linear
    else:
        signal_at_rx_mv = signal_mv

    # --- Noise budget ---
    isi_residual_mv = max(0.0, isi_penalty_mv - ctle_benefit_mv - dfe_benefit_mv - tx_deemph_benefit_mv)
    crosstalk_mv = len(channel.crosstalk_aggressors) * 5.0  # rough per-aggressor
    jitter_mv = nyquist_ghz * 0.5  # rough jitter penalty scales with frequency
    ild_penalty_mv = ild_penalty_db * 8.0

    total_noise_mv = math.sqrt(
        isi_residual_mv ** 2 + crosstalk_mv ** 2 + jitter_mv ** 2 + ild_penalty_mv ** 2
    )

    # Floor noise to avoid division by zero
    total_noise_mv = max(total_noise_mv, 1.0)

    # --- COM ---
    com_db = 20.0 * math.log10(signal_at_rx_mv / total_noise_mv)

    # --- Eye dimensions (rough estimates) ---
    eye_height_mv = max(0.0, 2.0 * (signal_at_rx_mv - total_noise_mv))
    ui_ps = 1e6 / channel.data_rate_gbps  # unit interval in ps
    eye_width_ps = max(0.0, ui_ps * (1.0 - min(total_il_db / 40.0, 0.8)))

    # --- PAM4 penalty ---
    if channel.modulation.value == "PAM4":
        com_db -= 9.5  # PAM4 has ~9.5 dB SNR penalty vs NRZ
        eye_height_mv /= 3.0
        if com_db < 3.0:
            warnings.append("PAM4 modulation significantly reduces margin — consider NRZ if data rate allows.")

    # --- Warnings ---
    if total_il_db > 25.0:
        warnings.append(f"Total insertion loss {total_il_db:.1f} dB exceeds 25 dB — channel may not close.")
    if not channel.segments:
        warnings.append("No channel segments defined — result is a placeholder.")

    passed = com_db >= 3.0

    if not passed:
        warnings.append(f"COM {com_db:.1f} dB is below 3 dB pass threshold.")

    return COMResult(
        com_db=round(com_db, 2),
        passed=passed,
        eye_height_mv=round(eye_height_mv, 1),
        eye_width_ps=round(eye_width_ps, 1),
        total_il_db=round(total_il_db, 2),
        rl_db=round(rl_db, 2),
        warnings=warnings,
    )
