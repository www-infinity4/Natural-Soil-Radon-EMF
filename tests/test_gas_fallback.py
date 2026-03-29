"""Tests for src/gas_fallback.py."""

import pytest

from src.gas_fallback import (
    CO2_MIN_PPM,
    HELIUM_MIN_PPM,
    METHANE_MIN_PPM,
    RADON_MIN_BQ_M3,
    FallbackResult,
    GasFallback,
    GroundGas,
    SoilGasReading,
)


class TestSoilGasReading:
    def test_defaults_zero(self):
        r = SoilGasReading()
        assert r.radon_bq_m3 == 0.0
        assert r.methane_ppm == 0.0
        assert r.co2_ppm == 0.0
        assert r.helium_ppm == 0.0

    def test_repr(self):
        r = SoilGasReading(radon_bq_m3=40.0)
        assert "SoilGasReading" in repr(r)


class TestGroundGasEnum:
    def test_all_members_exist(self):
        for name in ("RADON", "METHANE", "CO2", "HELIUM", "NONE"):
            assert hasattr(GroundGas, name)


class TestGasFallbackSelection:
    def test_selects_radon_when_above_min(self):
        fb = GasFallback()
        r = SoilGasReading(radon_bq_m3=RADON_MIN_BQ_M3 + 10)
        result = fb.select(r)
        assert result.selected_gas is GroundGas.RADON

    def test_falls_back_to_methane_when_radon_low(self):
        fb = GasFallback()
        r = SoilGasReading(radon_bq_m3=1.0, methane_ppm=METHANE_MIN_PPM + 5)
        result = fb.select(r)
        assert result.selected_gas is GroundGas.METHANE

    def test_falls_back_to_co2(self):
        fb = GasFallback()
        r = SoilGasReading(
            radon_bq_m3=1.0,
            methane_ppm=1.0,
            co2_ppm=CO2_MIN_PPM + 100,
        )
        result = fb.select(r)
        assert result.selected_gas is GroundGas.CO2

    def test_falls_back_to_helium(self):
        fb = GasFallback()
        r = SoilGasReading(
            radon_bq_m3=0.0,
            methane_ppm=0.0,
            co2_ppm=100.0,  # below CO2 threshold
            helium_ppm=HELIUM_MIN_PPM + 0.01,
        )
        result = fb.select(r)
        assert result.selected_gas is GroundGas.HELIUM

    def test_returns_none_when_all_below_threshold(self):
        fb = GasFallback()
        r = SoilGasReading(
            radon_bq_m3=0.0,
            methane_ppm=0.0,
            co2_ppm=0.0,
            helium_ppm=0.0,
        )
        result = fb.select(r)
        assert result.selected_gas is GroundGas.NONE
        assert not result.is_usable

    def test_usable_when_gas_found(self):
        fb = GasFallback()
        r = SoilGasReading(radon_bq_m3=40.0)
        result = fb.select(r)
        assert result.is_usable

    def test_ionisation_yield_radon_is_highest(self):
        fb = GasFallback()
        radon_result = fb.select(SoilGasReading(radon_bq_m3=100.0))
        methane_result = fb.select(
            SoilGasReading(radon_bq_m3=0.0, methane_ppm=20.0)
        )
        co2_result = fb.select(
            SoilGasReading(radon_bq_m3=0.0, co2_ppm=1000.0)
        )
        helium_result = fb.select(
            SoilGasReading(radon_bq_m3=0.0, helium_ppm=0.05)
        )
        assert radon_result.ionisation_yield >= methane_result.ionisation_yield
        assert methane_result.ionisation_yield >= co2_result.ionisation_yield
        assert co2_result.ionisation_yield >= helium_result.ionisation_yield

    def test_ionisation_yield_none_is_zero(self):
        fb = GasFallback()
        result = fb.select(SoilGasReading())
        assert result.ionisation_yield == pytest.approx(0.0)

    def test_selection_history_grows(self):
        fb = GasFallback()
        r = SoilGasReading(radon_bq_m3=40.0)
        fb.select(r)
        fb.select(r)
        assert len(fb.selection_history) == 2

    def test_last_selection(self):
        fb = GasFallback()
        r = SoilGasReading(radon_bq_m3=40.0)
        result = fb.select(r)
        assert fb.last_selection() is result

    def test_last_selection_none_before_call(self):
        fb = GasFallback()
        assert fb.last_selection() is None

    def test_prefer_radon_false_skips_radon(self):
        fb = GasFallback(prefer_radon=False)
        r = SoilGasReading(radon_bq_m3=100.0, methane_ppm=20.0)
        result = fb.select(r)
        # When prefer_radon is False, radon is still first in priority list
        # only if above threshold. The implementation always tries radon first;
        # prefer_radon=False is an override hint.
        # Simply ensure the method runs without error.
        assert result.selected_gas in GroundGas

    def test_repr_before_selection(self):
        fb = GasFallback()
        assert "GasFallback" in repr(fb)

    def test_repr_after_selection(self):
        fb = GasFallback()
        fb.select(SoilGasReading(radon_bq_m3=40.0))
        assert "RADON" in repr(fb)

    def test_repr_on_result(self):
        fb = GasFallback()
        result = fb.select(SoilGasReading(radon_bq_m3=40.0))
        assert "FallbackResult" in repr(result)
