"""
radon_beacon.py
---------------
Beacon + dual-pole synchronisation layer for the Natural Soil Radon EMF
signal-tractor system.

Rn-222 alpha-decay energy: ~5.5 MeV.
The underground pole (PRIMARY) pulses a low-energy carrier wave tuned to that
decay signature.  The aboveground pole (SECONDARY) listens and replies on the
exact harmonic frequency so both poles "talk" to each other and the magnetic
flux grows exponentially in the zone between them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RADON_ALPHA_MEV: float = 5.5          # MeV — Rn-222 dominant alpha energy
SPEED_OF_LIGHT_MS: float = 3.0e8     # m/s
BASE_CARRIER_HZ: float = 1.329e21    # Hz  ≈ E/h for 5.5 MeV (h = Planck const)
HARMONIC_MULTIPLIER: float = 2.0     # aboveground pole replies on 2nd harmonic

# Minimum signal strength (normalised 0–1) required to declare poles "synced"
SYNC_THRESHOLD: float = 0.72


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class PoleRole(Enum):
    """Physical role of a pole in the dual-pole system."""
    PRIMARY = auto()    # underground beacon; pulses carrier wave
    SECONDARY = auto()  # aboveground (drone-mounted); listens + replies


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PulsePacket:
    """A single electromagnetic pulse packet emitted by a pole."""
    frequency_hz: float
    energy_mev: float
    phase_rad: float = 0.0
    is_ionising: bool = True

    def harmonic(self, multiplier: float = HARMONIC_MULTIPLIER) -> "PulsePacket":
        """Return a new packet on the requested harmonic frequency."""
        return PulsePacket(
            frequency_hz=self.frequency_hz * multiplier,
            energy_mev=self.energy_mev * multiplier,
            phase_rad=self.phase_rad,
            is_ionising=self.is_ionising,
        )

    def __repr__(self) -> str:
        return (
            f"PulsePacket(freq={self.frequency_hz:.3e} Hz, "
            f"energy={self.energy_mev:.2f} MeV, "
            f"phase={self.phase_rad:.4f} rad)"
        )


@dataclass
class SyncState:
    """Represents the current synchronisation state between both poles."""
    is_synced: bool = False
    signal_strength: float = 0.0          # normalised 0–1
    phase_delta_rad: float = 0.0          # phase difference between poles
    flux_gain_db: float = 0.0             # exponential magnetic flux gain (dB)
    pulse_count: int = 0

    def __repr__(self) -> str:
        status = "SYNCED" if self.is_synced else "SEARCHING"
        return (
            f"SyncState({status}, strength={self.signal_strength:.3f}, "
            f"flux_gain={self.flux_gain_db:.1f} dB, pulses={self.pulse_count})"
        )


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class RadonBeacon:
    """
    Models one pole (PRIMARY or SECONDARY) in the dual-pole beacon system.

    The PRIMARY pole emits a carrier wave tuned to radon's alpha-decay
    signature.  The SECONDARY pole receives that signal, generates a harmonic
    reply, and both poles exchange packets until they reach synchronisation.

    Parameters
    ----------
    role :
        Whether this pole is the underground PRIMARY or aboveground SECONDARY.
    depth_m :
        Deployment depth (positive = below ground, negative = above ground).
    radon_concentration_bq_m3 :
        Measured local radon activity in Bq/m³ used to scale the carrier
        pulse energy.
    """

    def __init__(
        self,
        role: PoleRole,
        depth_m: float,
        radon_concentration_bq_m3: float = 40.0,
    ) -> None:
        self.role = role
        self.depth_m = depth_m
        self.radon_concentration_bq_m3 = radon_concentration_bq_m3

        self._sync_state = SyncState()
        self._paired_beacon: Optional["RadonBeacon"] = None
        self._pulse_log: list[PulsePacket] = []

    # ------------------------------------------------------------------
    # Pairing
    # ------------------------------------------------------------------

    def pair_with(self, other: "RadonBeacon") -> None:
        """
        Physically pair this beacon with its counterpart.

        A PRIMARY must be paired with a SECONDARY and vice-versa.
        """
        if self.role == other.role:
            raise ValueError(
                f"Cannot pair two {self.role.name} poles. "
                "Pair a PRIMARY with a SECONDARY."
            )
        self._paired_beacon = other
        other._paired_beacon = self  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Carrier-wave generation
    # ------------------------------------------------------------------

    def _scale_energy(self) -> float:
        """
        Scale the nominal alpha energy by local radon activity.

        A higher Bq/m³ reading means more decaying atoms are available to
        couple with the resonance field; we apply a log-normalised boost.
        """
        if self.radon_concentration_bq_m3 <= 0:
            return RADON_ALPHA_MEV * 0.1
        boost = 1.0 + 0.1 * math.log1p(self.radon_concentration_bq_m3 / 40.0)
        return RADON_ALPHA_MEV * boost

    def emit_carrier(self) -> PulsePacket:
        """
        Emit a carrier-wave pulse tuned to radon's alpha-decay signature.

        Only the PRIMARY pole should initiate; the SECONDARY replies via
        :meth:`reply_on_harmonic`.
        """
        if self.role is not PoleRole.PRIMARY:
            raise RuntimeError(
                "Only the PRIMARY (underground) pole initiates the carrier wave."
            )
        packet = PulsePacket(
            frequency_hz=BASE_CARRIER_HZ,
            energy_mev=self._scale_energy(),
            phase_rad=0.0,
            is_ionising=True,
        )
        self._pulse_log.append(packet)
        return packet

    def reply_on_harmonic(self, received: PulsePacket) -> PulsePacket:
        """
        Receive a carrier packet and reply on the harmonic frequency.

        Only the SECONDARY pole should call this method.
        """
        if self.role is not PoleRole.SECONDARY:
            raise RuntimeError(
                "Only the SECONDARY (aboveground) pole generates the harmonic reply."
            )
        reply = received.harmonic(HARMONIC_MULTIPLIER)
        # Phase reply is shifted by π/4 to set up constructive interference
        reply.phase_rad = received.phase_rad + math.pi / 4
        self._pulse_log.append(reply)
        return reply

    # ------------------------------------------------------------------
    # Synchronisation handshake
    # ------------------------------------------------------------------

    def synchronise(self, max_iterations: int = 20) -> SyncState:
        """
        Run the full synchronisation handshake between this pole and its pair.

        Each iteration the PRIMARY emits a carrier; the SECONDARY replies on
        the harmonic; the resulting magnetic flux grows exponentially.

        Returns
        -------
        SyncState
            Final synchronisation state after *max_iterations* or early
            convergence.
        """
        if self._paired_beacon is None:
            raise RuntimeError("Beacon has not been paired. Call pair_with() first.")
        if self.role is not PoleRole.PRIMARY:
            raise RuntimeError("synchronise() must be called on the PRIMARY beacon.")

        secondary = self._paired_beacon
        strength = 0.0
        flux_db = 0.0

        for i in range(1, max_iterations + 1):
            carrier = self.emit_carrier()
            _ = secondary.reply_on_harmonic(carrier)

            # Signal strength grows with radon concentration and iteration count;
            # saturates towards 1.0 via exponential approach.
            radon_factor = min(
                1.0, self.radon_concentration_bq_m3 / 100.0
            )
            strength = 1.0 - math.exp(-0.25 * i * radon_factor)

            # Exponential flux gain: each paired pulse amplifies the previous
            # by the constructive interference coefficient.
            flux_db = 10.0 * math.log10(1.0 + i * radon_factor)

            # Phase delta decreases (poles lock) as iterations progress
            phase_delta = math.pi / (1 + i)

            self._sync_state = SyncState(
                is_synced=(strength >= SYNC_THRESHOLD),
                signal_strength=strength,
                phase_delta_rad=phase_delta,
                flux_gain_db=flux_db,
                pulse_count=i * 2,  # one carrier + one harmonic per iteration
            )

            if self._sync_state.is_synced:
                break

        return self._sync_state

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def sync_state(self) -> SyncState:
        """Current synchronisation state."""
        return self._sync_state

    @property
    def pulse_log(self) -> list[PulsePacket]:
        """All packets emitted by this pole (read-only copy)."""
        return list(self._pulse_log)

    def __repr__(self) -> str:
        return (
            f"RadonBeacon(role={self.role.name}, depth={self.depth_m} m, "
            f"radon={self.radon_concentration_bq_m3} Bq/m³)"
        )
