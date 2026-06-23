"""Integration tests for Research options state."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    mock = MagicMock()
    mock.query.return_value = []
    mock.execute.return_value = None
    return mock


@pytest.mark.integration
class TestOptionsStateExpiration:
    def test_get_default_expiration_papi_profile(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.options_state import OptionsState
            state = OptionsState()

            today = datetime.now().date()
            exp_7d = (today + timedelta(days=7)).strftime("%Y-%m-%d")
            exp_14d = (today + timedelta(days=14)).strftime("%Y-%m-%d")
            exp_30d = (today + timedelta(days=30)).strftime("%Y-%m-%d")
            exp_45d = (today + timedelta(days=45)).strftime("%Y-%m-%d")

            expirations = [exp_7d, exp_14d, exp_30d, exp_45d]

            result = state._get_default_expiration_for_profile(expirations, "2_weeks")

            assert result in [exp_7d, exp_14d]

    def test_get_default_expiration_tio_profile(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.options_state import OptionsState
            state = OptionsState()

            today = datetime.now().date()
            exp_14d = (today + timedelta(days=14)).strftime("%Y-%m-%d")
            exp_30d = (today + timedelta(days=30)).strftime("%Y-%m-%d")
            exp_45d = (today + timedelta(days=45)).strftime("%Y-%m-%d")
            exp_90d = (today + timedelta(days=90)).strftime("%Y-%m-%d")

            expirations = [exp_14d, exp_30d, exp_45d, exp_90d]

            result = state._get_default_expiration_for_profile(
                expirations, "1_2_months"
            )

            assert result in [exp_30d, exp_45d]

    def test_get_default_expiration_franky_profile(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.options_state import OptionsState

            state = OptionsState()

            expirations = ["2025-02-21", "2025-03-21", "2025-04-18"]

            result = state._get_default_expiration_for_profile(expirations, "varies")

            assert result == "2025-02-21"

    def test_get_default_expiration_fallback_to_first(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.options_state import OptionsState
            state = OptionsState()

            today = datetime.now().date()
            exp_90d = (today + timedelta(days=90)).strftime("%Y-%m-%d")
            exp_120d = (today + timedelta(days=120)).strftime("%Y-%m-%d")

            expirations = [exp_90d, exp_120d]

            result = state._get_default_expiration_for_profile(expirations, "2_weeks")

            assert result == exp_90d

    def test_get_default_expiration_empty_list(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.options_state import OptionsState

            state = OptionsState()

            result = state._get_default_expiration_for_profile([], "2_weeks")

            assert result == ""


@pytest.mark.integration
class TestOptionsStateInterestingStrikes:
    def test_get_interesting_strikes_includes_atm(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.options_state import OptionsState

            state = OptionsState()

            strikes = [160.0, 165.0, 170.0, 175.0, 180.0, 185.0, 190.0]
            current_price = 175.50

            result = state._get_interesting_strikes(
                strikes, current_price, 190.0, 160.0, 200.0
            )

            atm_strikes = [s for s in result if s.get("is_atm")]
            assert len(atm_strikes) == 1
            assert atm_strikes[0]["annotation"] == "ATM"

    def test_get_interesting_strikes_includes_range_high(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.options_state import OptionsState

            state = OptionsState()

            strikes = [160.0, 165.0, 170.0, 175.0, 180.0, 185.0, 189.0, 190.0]
            current_price = 175.50
            range_high = 190.0

            result = state._get_interesting_strikes(
                strikes, current_price, range_high, 160.0, 200.0
            )

            range_high_strikes = [
                s for s in result if s.get("annotation") == "Range High"
            ]
            assert len(range_high_strikes) >= 1

    def test_get_interesting_strikes_respects_bounds(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.options_state import OptionsState

            state = OptionsState()

            strikes = [100.0, 150.0, 170.0, 175.0, 180.0, 200.0, 250.0]
            current_price = 175.0

            result = state._get_interesting_strikes(
                strikes, current_price, 200.0, 150.0, 210.0
            )

            result_strikes = [s["strike"] for s in result]
            lower_bound = current_price * 0.90
            upper_bound = current_price * 1.10

            for strike in result_strikes:
                assert lower_bound <= strike <= upper_bound

    def test_get_interesting_strikes_empty_on_no_current_price(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.options_state import OptionsState

            state = OptionsState()

            strikes = [170.0, 175.0, 180.0]

            result = state._get_interesting_strikes(strikes, 0, 190.0, 160.0, 200.0)

            assert result == []


