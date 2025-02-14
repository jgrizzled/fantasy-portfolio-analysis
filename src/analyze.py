from datetime import datetime
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
      - The portfolio with the highest total return (since start) gets +1
      - The portfolio with the lowest max drawdown (since start) gets +1
    Ties get +1 points for all portfolios that tie.
    """
    df = daily_values_df.copy()
    df['YearMonth'] = df.index.to_period('M')

    portfolios = [c for c in df.columns if c != 'YearMonth']
    monthly_scores_dict = {}  # key: YearMonth, value: dict of portfolio scores for that month

    # Determine the current month period to skip incomplete month scoring
    current_period = pd.Timestamp.now().to_period('M')

    for (ym), group in df.groupby('YearMonth'):
        if ym == current_period:
            # Skip calculating scores for the current month since it is not finished
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

        # highest total return => we want the portfolio(s) with the largest value
        max_return = total_returns.max()
        winners_return = total_returns[total_returns == max_return].index

        # lowest overall max drawdown => means the max drawdown is the least negative
        dd_series = pd.Series(period_drawdowns)
        best_dd_val = dd_series.max()  # the "least negative" is the max
        winners_dd = dd_series[dd_series == best_dd_val].index

        # Build a score for this month (defaulting to zero for every portfolio)
        month_score = {p: 0 for p in portfolios}
        for w in winners_return:
            month_score[w] += 1
        for w in winners_dd:
            month_score[w] += 1

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
    start_date = datetime.strptime(cfg['start_date'], '%Y-%m-%d')
    today = datetime.today()
    end_date = (
        datetime.strptime(cfg['end_date'], '%Y-%m-%d') if cfg['end_date'] else today
    )
    if end_date > today:
        end_date = today
    if not start_date:
        raise ValueError('Must provide a valid start_date.')
    if not end_date:
        end_date = today
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

    # Determine winner
    stats_df = stats_df.sort_values(by=['score', 'rebalances'], ascending=[False, True])
    winner = stats_df.iloc[0]['portfolio']

    return {
        'values_df': values_df,
        'stats_df': stats_df,
        'monthly_scores_df': monthly_scores_df,
        'winner': winner,
    }
