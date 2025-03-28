from datetime import datetime, timedelta
import pytz
from zoneinfo import ZoneInfo
from utils import (
    compute_max_drawdown,
    compute_sharpe_ratio,
)
from backtest import backtest_portfolio
import pandas as pd
from data import get_price_data


def get_monthly_scores(daily_values_df: pd.DataFrame) -> pd.DataFrame:
    """
    daily_values_df: A DataFrame where each column is a portfolio's daily equity.
    Returns a DataFrame with monthly score totals per portfolio.
    Scoring per month:
      - Portfolios are ranked by total return (since start)
      - Portfolios are ranked by max drawdown (since start)
    The final score for each portfolio is the sum of its ranks in both categories.
    Higher ranks indicate better performance.
    """
    df = daily_values_df.copy()
    df['YearMonth'] = df.index.to_period('M')

    portfolios = [c for c in df.columns if c != 'YearMonth']
    monthly_scores_dict = {}  # key: YearMonth, value: dict of portfolio scores for that month

    # Determine the current month period to skip incomplete month scoring
    current_period = pd.Timestamp.now().to_period('M')

    # Get the first day of data to check for partial first month
    first_day = df.index[0]
    first_month = first_day.to_period('M')

    for (ym), group in df.groupby('YearMonth'):
        # Skip current month and first month if it's partial
        if ym == current_period:
            continue

        if ym == first_month and first_day.day > 5:
            continue

        start_values = df.iloc[0][portfolios]
        end_values = group.iloc[-1][portfolios]
        total_returns = (end_values / start_values) - 1.0

        current_month_end = group.index[-1]
        data_until_now = df.loc[:current_month_end]

        period_drawdowns = {}
        for p in portfolios:
            curve = data_until_now[p]
            dd = compute_max_drawdown(curve)
            period_drawdowns[p] = dd

        # Convert to series for easier ranking
        dd_series = pd.Series(period_drawdowns)
        return_ranks = total_returns.rank(ascending=True)
        dd_ranks = dd_series.rank(ascending=True)

        # Sum the ranks for total score
        month_score = {p: return_ranks[p] + dd_ranks[p] for p in portfolios}
        monthly_scores_dict[ym] = month_score

    # Create a DataFrame where index is YearMonth and columns are portfolios
    monthly_scores_df = pd.DataFrame.from_dict(monthly_scores_dict, orient='index')
    monthly_scores_df = monthly_scores_df[portfolios]
    return monthly_scores_df


def analyze(cfg, price_data=None):
    """
    Runs the portfolio analysis and returns the results.

    Args:
        cfg (dict): Configuration dictionary containing portfolio settings
        price_data (DataFrame, optional): Pre-downloaded price data. If None, will download.
    """
    # Parse start/end dates
    start_date = datetime.strptime(cfg['start_date'], '%Y-%m-%d').replace(
        tzinfo=ZoneInfo('America/New_York'), hour=16, minute=0, second=0, microsecond=0
    )

    # Set time to market close in NY (4:00 PM ET)
    ny_tz = pytz.timezone('America/New_York')
    current_time = datetime.now(ny_tz)
    today = current_time.replace(hour=16, minute=0, second=0, microsecond=0)

    # Determine latest market close based on current NY time
    if current_time.hour < 16:  # Before 4pm NY time
        latest_market_close = today - timedelta(days=1)
    else:  # 4pm or later NY time
        latest_market_close = today

    # If end_date specified in config, use it, otherwise use latest market close
    if cfg['end_date']:
        end_date = datetime.strptime(cfg['end_date'], '%Y-%m-%d').replace(
            tzinfo=ZoneInfo('America/New_York'),
            hour=16,
            minute=0,
            second=0,
            microsecond=0,
        )
    else:
        end_date = latest_market_close

    if not start_date:
        raise ValueError('Must provide a valid start_date.')
    if start_date >= end_date:
        raise ValueError('start_date must be before end_date.')

    # Gather all tickers
    all_tickers = set()
    for pf in cfg['portfolios']:
        for date_str, settings in pf['settings_history'].items():
            for k, v in settings.items():
                if k not in ('auto_rebalance',):
                    all_tickers.add(k)
    all_tickers = sorted(list(all_tickers))

    if not all_tickers:
        raise ValueError('No tickers found in portfolios.')

    if price_data is None:
        price_data = get_price_data(all_tickers, start_date, end_date)

    all_dates = price_data.index.unique().tolist()

    # Run backtests for each portfolio
    portfolio_values = {}
    rebalances_count = {}

    for pf in cfg['portfolios']:
        name = pf['name']
        vals, rebs = backtest_portfolio(
            pf, price_data, all_dates, cfg['initial_capital']
        )
        portfolio_values[name] = vals
        rebalances_count[name] = rebs

    values_df = pd.DataFrame(portfolio_values)

    # Compute stats for each portfolio
    stats_rows = []
    for name in values_df.columns:
        series = values_df[name]
        final_val = series.dropna().iloc[-1]
        total_return = final_val / cfg['initial_capital'] - 1.0

        maxdd = compute_max_drawdown(series)
        sharpe = compute_sharpe_ratio(series)
        stats_rows.append(
            {
                'portfolio': name,
                'total_return': total_return,
                'maxdd': maxdd,
                'sharpe': sharpe,
                'rebalances': rebalances_count[name],
            }
        )
    stats_df = pd.DataFrame(stats_rows)

    # Score portfolios: get monthly scores and sum to get total scores per portfolio
    monthly_scores_df = get_monthly_scores(values_df)
    total_scores = monthly_scores_df.sum(axis=0)
    stats_df['score'] = stats_df['portfolio'].map(total_scores)

    # Determine winners
    stats_df = stats_df.sort_values(by=['score', 'rebalances'], ascending=[False, True])
    max_score = stats_df['score'].max()
    winners = stats_df[stats_df['score'] == max_score]['portfolio'].tolist()

    return {
        'values_df': values_df,
        'stats_df': stats_df,
        'monthly_scores_df': monthly_scores_df,
        'winners': winners,  # Now returns a list of all winning portfolios
    }
