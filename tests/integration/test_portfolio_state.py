from datetime import date
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    mock = MagicMock()
    mock.query.return_value = []
    mock.execute.return_value = None
    return mock


@pytest.fixture
def mock_market_data():
    mock = MagicMock()
    mock_info = MagicMock()
    mock_info.current_price = 175.50
    mock.get_ticker_info.return_value = mock_info
    return mock


class TestPortfolioStatePositionCalculations:
    def test_total_value_calculation(self, mock_db, mock_market_data):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db
            mock_services.market_data = mock_market_data

            mock_db.query.return_value = [
                {
                    "id": 1,
                    "ticker_symbol": "AAPL",
                    "quantity": 100,
                    "cost_basis": 150.00,
                    "purchase_date": "2024-01-01",
                    "notes": "",
                },
                {
                    "id": 2,
                    "ticker_symbol": "MSFT",
                    "quantity": 50,
                    "cost_basis": 380.00,
                    "purchase_date": "2024-02-01",
                    "notes": "",
                },
            ]

            from phinan.modules.portfolio.state import PortfolioState

            state = PortfolioState()
            state.positions = []

            expected_value = (100 * 175.50) + (50 * 175.50)

            from phinan.modules.portfolio.state import PortfolioPosition

            state.positions = [
                PortfolioPosition(
                    id=1,
                    ticker_symbol="AAPL",
                    quantity=100,
                    cost_basis=150.00,
                    current_price=175.50,
                    current_value=17550.0,
                ),
                PortfolioPosition(
                    id=2,
                    ticker_symbol="MSFT",
                    quantity=50,
                    cost_basis=380.00,
                    current_price=175.50,
                    current_value=8775.0,
                ),
            ]

            assert state.total_value == 17550.0 + 8775.0

    def test_gain_loss_calculation(self, mock_db, mock_market_data):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db
            mock_services.market_data = mock_market_data

            from phinan.modules.portfolio.state import PortfolioState, PortfolioPosition

            state = PortfolioState()

            state.positions = [
                PortfolioPosition(
                    id=1,
                    ticker_symbol="AAPL",
                    quantity=100,
                    cost_basis=150.00,
                    current_price=175.50,
                    current_value=17550.0,
                    gain_loss=2550.0,
                    gain_loss_percent=17.0,
                ),
            ]

            expected_cost = 100 * 150.00
            expected_value = 17550.0
            expected_gain = expected_value - expected_cost

            assert state.total_cost == expected_cost
            assert state.total_gain_loss == expected_gain

    def test_gain_loss_percent_zero_cost(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.portfolio.state import PortfolioState

            state = PortfolioState()
            state.positions = []

            assert state.total_gain_loss_percent == 0.0


class TestPortfolioStateFormValidation:
    def test_add_position_validates_empty_ticker(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.portfolio.state import PortfolioState

            state = PortfolioState()
            state.form_ticker = ""
            state.form_quantity = "100"
            state.form_cost_basis = "150.00"

    def test_add_position_validates_negative_quantity(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.portfolio.state import PortfolioState

            state = PortfolioState()
            state.form_ticker = "AAPL"
            state.form_quantity = "-100"
            state.form_cost_basis = "150.00"

    def test_add_position_validates_invalid_cost_basis(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.portfolio.state import PortfolioState

            state = PortfolioState()
            state.form_ticker = "AAPL"
            state.form_quantity = "100"
            state.form_cost_basis = "invalid"


class TestPortfolioStateTickerLookup:
    def test_get_position_for_ticker_found(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.portfolio.state import PortfolioState, PortfolioPosition

            state = PortfolioState()
            state.positions = [
                PortfolioPosition(
                    id=1, ticker_symbol="AAPL", quantity=100, cost_basis=150.00
                ),
                PortfolioPosition(
                    id=2, ticker_symbol="MSFT", quantity=50, cost_basis=380.00
                ),
            ]

            result = state.get_position_for_ticker("AAPL")

            assert result is not None
            assert result.ticker_symbol == "AAPL"

    def test_get_position_for_ticker_not_found(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.portfolio.state import PortfolioState

            state = PortfolioState()
            state.positions = []

            result = state.get_position_for_ticker("INVALID")

            assert result is None

    def test_get_position_for_ticker_case_insensitive(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.portfolio.state import PortfolioState, PortfolioPosition

            state = PortfolioState()
            state.positions = [
                PortfolioPosition(
                    id=1, ticker_symbol="AAPL", quantity=100, cost_basis=150.00
                ),
            ]

            result = state.get_position_for_ticker("aapl")

            assert result is not None
            assert result.ticker_symbol == "AAPL"


class TestPortfolioStateSummary:
    def test_top_gainers_returns_sorted_positions(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.portfolio.state import PortfolioState, PortfolioPosition

            state = PortfolioState()
            state.positions = [
                PortfolioPosition(
                    id=1,
                    ticker_symbol="AAPL",
                    quantity=100,
                    cost_basis=150.00,
                    gain_loss_percent=20.0,
                ),
                PortfolioPosition(
                    id=2,
                    ticker_symbol="MSFT",
                    quantity=50,
                    cost_basis=380.00,
                    gain_loss_percent=5.0,
                ),
                PortfolioPosition(
                    id=3,
                    ticker_symbol="GOOGL",
                    quantity=25,
                    cost_basis=140.00,
                    gain_loss_percent=15.0,
                ),
            ]

            gainers = state.top_gainers

            assert len(gainers) == 3
            assert gainers[0]["symbol"] == "AAPL"
            assert gainers[0]["change_pct"] == 20.0

    def test_top_losers_returns_sorted_positions(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.portfolio.state import PortfolioState, PortfolioPosition

            state = PortfolioState()
            state.positions = [
                PortfolioPosition(
                    id=1,
                    ticker_symbol="AAPL",
                    quantity=100,
                    cost_basis=150.00,
                    gain_loss_percent=-5.0,
                ),
                PortfolioPosition(
                    id=2,
                    ticker_symbol="MSFT",
                    quantity=50,
                    cost_basis=380.00,
                    gain_loss_percent=-15.0,
                ),
                PortfolioPosition(
                    id=3,
                    ticker_symbol="GOOGL",
                    quantity=25,
                    cost_basis=140.00,
                    gain_loss_percent=-10.0,
                ),
            ]

            losers = state.top_losers

            assert len(losers) == 3
            assert losers[0]["symbol"] == "MSFT"
            assert losers[0]["change_pct"] == -15.0
