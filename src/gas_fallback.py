"""
gas_fallback.py
---------------
Fallback-gas selector for the Natural Soil Radon EMF signal-tractor.

When local radon activity is too low to bootstrap trepel-resonance the system
auto-switches to the next most abundant ionisable ground gas.  The poles use
the same electron-stripping / resonance technique regardless of which gas is
present — they just need something ionisable in the pore space to establish
conductivity.

Priority order (richest to rarest in typical agricultural soils):
    1. Rn-222  (radon)    — preferred; alpha decay at 5.5 MeV
    2. CH₄     (methane)  — microbial/anaerobic activity
    3. CO₂              — microbial respiration
    4. He-4    (helium)   — alpha-decay daughter; trace quantities
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Minimum usable activity / concentration thresholds
# ---------------------------------------------------------------------------

# Radon below this Bq/m³ → switch away from radon
RADON_MIN_BQ_M3: float = 20.0
# Methane below this ppm → skip methane
METHANE_MIN_PPM: float = 5.0
# CO₂ below this ppm → skip CO₂  (atmospheric baseline ≈ 420 ppm)
CO2_MIN_PPM: float = 500.0
# Helium is always present (trace); treated as last resort with a fixed floor
HELIUM_MIN_PPM: float = 0.01


# ---------------------------------------------------------------------------
# Enumerations & data classes
# ---------------------------------------------------------------------------

class GroundGas(Enum):
    """Ionisable ground gases usable as trepel-resonance bootstrap fuel."""
    RADON = auto()
    METHANE = auto()
    CO2 = auto()
    HELIUM = auto()
    NONE = auto()   # no suitable gas detected


@dataclass
class SoilGasReading:
    """One snapshot of subsurface gas concentrations."""
    radon_bq_m3: float = 0.0
    methane_ppm: float = 0.0
    co2_ppm: float = 0.0
    helium_ppm: float = 0.0

    def __repr__(self) -> str:
        return (
            f"SoilGasReading(Rn={self.radon_bq_m3:.1f} Bq/m³, "
            f"CH₄={self.methane_ppm:.1f} ppm, "
            f"CO₂={self.co2_ppm:.1f} ppm, "
            f"He={self.helium_ppm:.4f} ppm)"
        )


@dataclass
class FallbackResult:
    """Result of a gas-selection decision."""
    selected_gas: GroundGas
    reading: SoilGasReading
    ionisation_yield: float   # normalised 0–1; relative ease of stripping electrons

    @property
    def is_usable(self) -> bool:
        """True if a suitable gas was found."""
        return self.selected_gas is not GroundGas.NONE

    def __repr__(self) -> str:
        return (
            f"FallbackResult(gas={self.selected_gas.name}, "
            f"yield={self.ionisation_yield:.3f}, usable={self.is_usable})"
        )


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class GasFallback:
    """
    Selects the best available ground gas for trepel-resonance bootstrapping.

    The selector walks down the priority list (radon → methane → CO₂ → helium)
    and returns the first gas that meets its minimum-availability threshold.

    Parameters
    ----------
    prefer_radon :
        If True (default), radon is always the first choice when available.
    """

    # Relative ionisation yield for each gas (normalised to radon = 1.0)
    _IONISATION_YIELD: dict[GroundGas, float] = {
        GroundGas.RADON:   1.000,   # benchmark
        GroundGas.METHANE: 0.620,   # readily ionised but lower alpha coupling
        GroundGas.CO2:     0.480,   # moderate; CO₂⁺ ions still drive conductivity
        GroundGas.HELIUM:  0.310,   # trace quantities; weakest but reliable
        GroundGas.NONE:    0.000,
    }

    def __init__(self, prefer_radon: bool = True) -> None:
        self.prefer_radon = prefer_radon
        self._selection_history: list[FallbackResult] = []

    # ------------------------------------------------------------------
    # Core selection logic
    # ------------------------------------------------------------------

    def select(self, reading: SoilGasReading) -> FallbackResult:
        """
        Select the best available ionisable gas from *reading*.

        Parameters
        ----------
        reading :
            Current subsurface gas concentrations.

        Returns
        -------
        FallbackResult
            The chosen gas and its estimated ionisation yield.
        """
        selected = self._priority_select(reading)
        yield_val = self._IONISATION_YIELD[selected]

        # Scale yield by how far above the minimum threshold the reading is,
        # capped at 1.0 so we never claim more than radon's benchmark.
        if selected is GroundGas.RADON and reading.radon_bq_m3 > RADON_MIN_BQ_M3:
            yield_val = min(
                1.0,
                yield_val * (reading.radon_bq_m3 / RADON_MIN_BQ_M3) ** 0.3,
            )
        elif selected is GroundGas.METHANE and reading.methane_ppm > METHANE_MIN_PPM:
            yield_val = min(
                self._IONISATION_YIELD[GroundGas.RADON],
                yield_val * (reading.methane_ppm / METHANE_MIN_PPM) ** 0.2,
            )
        elif selected is GroundGas.CO2 and reading.co2_ppm > CO2_MIN_PPM:
            yield_val = min(
                self._IONISATION_YIELD[GroundGas.RADON],
                yield_val * (reading.co2_ppm / CO2_MIN_PPM) ** 0.15,
            )

        result = FallbackResult(
            selected_gas=selected,
            reading=reading,
            ionisation_yield=yield_val,
        )
        self._selection_history.append(result)
        return result

    def _priority_select(self, r: SoilGasReading) -> GroundGas:
        """Internal: walk the priority list and return the first viable gas."""
        if self.prefer_radon and r.radon_bq_m3 >= RADON_MIN_BQ_M3:
            return GroundGas.RADON
        if r.methane_ppm >= METHANE_MIN_PPM:
            return GroundGas.METHANE
        if r.co2_ppm >= CO2_MIN_PPM:
            return GroundGas.CO2
        if r.helium_ppm >= HELIUM_MIN_PPM:
            return GroundGas.HELIUM
        return GroundGas.NONE

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def selection_history(self) -> list[FallbackResult]:
        """All prior gas selections (read-only copy)."""
        return list(self._selection_history)

    def last_selection(self) -> Optional[FallbackResult]:
        """Most recent selection, or None if never called."""
        return self._selection_history[-1] if self._selection_history else None

    def __repr__(self) -> str:
        last = self.last_selection()
        gas = last.selected_gas.name if last else "—"
        return f"GasFallback(prefer_radon={self.prefer_radon}, last_gas={gas})"
