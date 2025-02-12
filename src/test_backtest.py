from backtest import backtest_portfolio
import datetime
from data import get_price_data


def _verify_backtest_results(
    config, expected_total_return, expected_maxdd, expected_rebalances, price_data
):
    """Helper function to verify backtest results."""
    expected_end_balance = config['initial_capital'] * (1 + expected_total_return)

    # Get the portfolio config from the test config
    portfolio_config = config['portfolios'][0]
    all_dates = price_data.index.unique().tolist()

    # Run the backtest directly
    portfolio_values, rebalance_count = backtest_portfolio(
        portfolio_config, price_data, all_dates, config['initial_capital']
    )

    # Calculate actual values
    actual_end_balance = portfolio_values.iloc[-1]
    actual_total_return = actual_end_balance / config['initial_capital'] - 1

    # Calculate max drawdown
    portfolio_values = portfolio_values.dropna()
    rolling_max = portfolio_values.expanding().max()
    drawdowns = portfolio_values / rolling_max - 1
    actual_maxdd = drawdowns.min()

    assert rebalance_count == expected_rebalances, (
        f"Number of rebalances {rebalance_count} doesn't match expected {expected_rebalances}"
    )

    tolerance = 0.1
    assert (
        abs(actual_end_balance - expected_end_balance)
        < expected_end_balance * tolerance
    ), (
        f"End balance {actual_end_balance:.2f} doesn't match expected {expected_end_balance}"
    )

    assert abs(actual_maxdd - expected_maxdd) < tolerance, (
        f"Maximum drawdown {actual_maxdd:.4f} doesn't match expected {expected_maxdd}"
    )

    assert abs(actual_total_return - expected_total_return) < tolerance, (
        f"Total return {actual_total_return:.4f} doesn't match expected {expected_total_return}"
    )


def test_simple():
    config = {
        'initial_capital': 10000.0,
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'portfolios': [
            {
                'name': 'Test Portfolio',
                'settings_history': {
                    '2024-01-01': {'auto_rebalance': 'none', 'SPY': 1.0},
                },
            },
        ],
    }
    tickers = ['SPY']
    start_date = datetime.datetime(2024, 1, 1)
    end_date = datetime.datetime(2024, 12, 31)
    price_data = get_price_data(tickers, start_date, end_date)
    _verify_backtest_results(
        config,
        expected_total_return=0.26,
        expected_maxdd=-0.0841,
        expected_rebalances=1,  # Initial rebalance only
        price_data=price_data,
    )


def test_multi():
    config = {
        'initial_capital': 10000.0,
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'portfolios': [
            {
                'name': 'Test Portfolio',
                'settings_history': {
                    '2024-01-01': {'auto_rebalance': 'none', 'SPY': 0.6, 'TLT': 0.4},
                },
            },
        ],
    }
    tickers = ['SPY', 'TLT']
    start_date = datetime.datetime(2024, 1, 1)
    end_date = datetime.datetime(2024, 12, 31)
    price_data = get_price_data(tickers, start_date, end_date)
    # Values from ycharts
    _verify_backtest_results(
        config,
        expected_total_return=9724.71 / 8656.30 - 1,
        expected_maxdd=-0.0542,
        expected_rebalances=1,  # Initial rebalance only
        price_data=price_data,
    )


def test_monthly_rebalance():
    config = {
        'initial_capital': 10000.0,
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'portfolios': [
            {
                'name': 'Test Portfolio',
                'settings_history': {
                    '2024-01-01': {
                        'auto_rebalance': 'monthly',
                        'MSTR': 0.5,
                        'TLT': 0.5,
                    },
                },
            },
        ],
    }
    tickers = ['MSTR', 'TLT']
    start_date = datetime.datetime(2024, 1, 1)
    end_date = datetime.datetime(2024, 12, 31)
    price_data = get_price_data(tickers, start_date, end_date)
    # Values from ycharts
    _verify_backtest_results(
        config,
        expected_total_return=9391.58 / 3757.88 - 1,
        expected_maxdd=-0.2866,
        expected_rebalances=12,
        price_data=price_data,
    )


def test_settings_change():
    config = {
        'initial_capital': 10000.0,
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'portfolios': [
            {
                'name': 'Test Portfolio',
                'settings_history': {
                    '2024-01-02': {'TLT': 1},
                    '2024-01-03': {'SPY': 1},
                },
            },
        ],
    }
    tickers = ['SPY', 'TLT']
    start_date = datetime.datetime(2024, 1, 1)
    end_date = datetime.datetime(2024, 12, 31)
    price_data = get_price_data(tickers, start_date, end_date)
    # Using same values from SPY test since it should be about the same
    _verify_backtest_results(
        config,
        expected_total_return=0.26,
        expected_maxdd=-0.0841,
        expected_rebalances=2,
        price_data=price_data,
    )


def test_auto_rebalance_change():
    config = {
        'initial_capital': 10000.0,
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'portfolios': [
            {
                'name': 'Test Portfolio',
                'settings_history': {
                    '2024-01-01': {
                        'auto_rebalance': 'none',
                        'MSTR': 0.5,
                        'TLT': 0.5,
                    },
                    '2024-01-03': {
                        'auto_rebalance': 'monthly',
                        'MSTR': 0.5,
                        'TLT': 0.5,
                    },
                },
            },
        ],
    }
    tickers = ['MSTR', 'TLT']
    start_date = datetime.datetime(2024, 1, 1)
    end_date = datetime.datetime(2024, 12, 31)
    price_data = get_price_data(tickers, start_date, end_date)
    # Using same values as in test_monthly_rebalance since it should be about the same
    _verify_backtest_results(
        config,
        expected_total_return=9391.58 / 3757.88 - 1,
        expected_maxdd=-0.2866,
        expected_rebalances=13,
        price_data=price_data,
    )


def test_auto_rebalance_change2():
    config = {
        'initial_capital': 10000.0,
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'portfolios': [
            {
                'name': 'Test Portfolio',
                'settings_history': {
                    '2024-01-01': {'auto_rebalance': 'monthly', 'SPY': 0.6, 'TLT': 0.4},
                    '2024-01-03': {'auto_rebalance': 'none', 'SPY': 0.6, 'TLT': 0.4},
                },
            },
        ],
    }
    tickers = ['SPY', 'TLT']
    start_date = datetime.datetime(2024, 1, 1)
    end_date = datetime.datetime(2024, 12, 31)
    price_data = get_price_data(tickers, start_date, end_date)
    # Using same values from test_multi since it should be about the same
    _verify_backtest_results(
        config,
        expected_total_return=9724.71 / 8656.30 - 1,
        expected_maxdd=-0.0542,
        expected_rebalances=2,
        price_data=price_data,
    )
