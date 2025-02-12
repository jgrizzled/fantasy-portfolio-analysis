from datetime import datetime, timedelta, date, time
from dateutil.relativedelta import relativedelta
import pandas as pd
import numpy as np


def get_next_rebalance_date(current_date, frequency='none'):
    """
    If 'daily', return the next trading day.
    If 'weekly', rebalance on next Friday.
    If 'monthly', rebalance on the last calendar day of the current month.
    If 'quarterly', rebalance on the last calendar day of the current quarter.
    If 'annually', rebalance on the last calendar day of the year.
    Else None (never auto rebalance).
    """
    if frequency == 'daily':
        return current_date + timedelta(days=1)
    if frequency == 'weekly':
        # move forward until we get to Friday
        # if current_date is Friday, then next rebalance is next week's Friday
        wday = current_date.weekday()  # Monday=0, Sunday=6
        days_until_friday = (4 - wday) % 7
        if days_until_friday == 0:
            days_until_friday = 7
        return current_date + timedelta(days=days_until_friday)
    if frequency == 'monthly':
        # next rebalance date is the last calendar day of the current month
        # or if current_date is last day, then next is last day of next month
        year = current_date.year
        month = current_date.month
        # start by going to 1st day of next month
        next_month_first = date(year, month, 1) + relativedelta(months=1)
        # then subtract 1 day to get last day of current month
        last_day_this_month = next_month_first - timedelta(days=1)
        # if current_date is already that last day, go to next month
        if current_date.date() >= last_day_this_month:
            # find last day of next month
            next_month_first_2 = date(year, month, 1) + relativedelta(months=2)
            last_day_next_month = next_month_first_2 - timedelta(days=1)
            return datetime.combine(last_day_next_month, time(0, 0))
        else:
            return datetime.combine(last_day_this_month, time(0, 0))

    if frequency == 'quarterly':
        # next rebalance date is the last calendar day of the current quarter
        # or if current_date is on/after that day, then next is the last day of the next quarter.
        quarter = (current_date.month - 1) // 3 + 1
        quarter_end_month = quarter * 3
        quarter_end_date = (
            date(current_date.year, quarter_end_month, 1)
            + relativedelta(months=1)
            - timedelta(days=1)
        )
        if current_date.date() >= quarter_end_date:
            next_quarter = quarter + 1
            next_year = current_date.year
            if next_quarter > 4:
                next_quarter = 1
                next_year += 1
            next_quarter_end_month = next_quarter * 3
            next_quarter_end_date = (
                date(next_year, next_quarter_end_month, 1)
                + relativedelta(months=1)
                - timedelta(days=1)
            )
            return datetime.combine(next_quarter_end_date, time(0, 0))
        else:
            return datetime.combine(quarter_end_date, time(0, 0))

    if frequency == 'annually':
        # next rebalance date is the last day of the year,
        # or if current_date is on/after Dec 31, then next is Dec 31 of the next year.
        year = current_date.year
        year_end_date = date(year, 12, 31)
        if current_date.date() >= year_end_date:
            year_end_date = date(year + 1, 12, 31)
        return datetime.combine(year_end_date, time(0, 0))

    return None  # fallback


def find_portfolio_settings_for_date(settings_history, current_date):
    """
    Among all the keys in settings_history (which are date strings),
    find the last setting that is <= current_date.
    Return that setting dict. If none applies, return None.
    """
    applicable_dates = []
    for date_str, settings in settings_history.items():
        d = datetime.strptime(date_str, '%Y-%m-%d')
        if d is not None and d <= current_date:
            applicable_dates.append((d, settings))
    if not applicable_dates:
        return None
    # pick the latest date that is <= current_date
    applicable_dates.sort(key=lambda x: x[0])
    return applicable_dates[-1][1]


# New helper function to extract and validate ticker weights
def prepare_tickers_weights(settings, portfolio_name, current_date):
    """
    Extract ticker weights from a settings dict, excluding the 'auto_rebalance' key,
    and ensure that the sum of weights does not exceed 1.0.
    """
    if settings is None:
        return {}
    tickers_weights = {k: v for k, v in settings.items() if k != 'auto_rebalance'}
    total_weight = sum(tickers_weights.values())
    if total_weight > 1.0:
        raise ValueError(f'Sum of weights > 1.0 for {portfolio_name} on {current_date}')
    return tickers_weights


# New helper function to execute rebalancing
def rebalance_portfolio(portfolio_value, price_row, tickers_weights, columns):
    """
    Given a portfolio_value, the current price_row, and a dict of ticker weights,
    computes the new holdings and remaining cash.
    """
    cash = portfolio_value
    holdings = {t: 0.0 for t in columns}
    for t, weight in tickers_weights.items():
        if t in columns:
            px = price_row[t]
            if not np.isnan(px):
                alloc = cash * weight
                shares = alloc // px
                cost = shares * px
                holdings[t] = shares
                cash -= cost
    return holdings, cash


def backtest_portfolio(portfolio_config, price_data, all_dates, initial_capital):
    """
    portfolio_config: dict with 'name' and 'settings_history'.
    price_data: DataFrame of daily adjusted prices for all tickers (columns).
    all_dates: sorted list of daily timestamps in the backtest range.
    initial_capital: float
    Returns a Series of daily portfolio values (aligned to all_dates),
    plus the total number of rebalances that occurred.
    """
    name = portfolio_config['name']
    settings_history = portfolio_config['settings_history']

    # track daily portfolio value
    daily_values = pd.Series(index=all_dates, dtype=float)

    # current shares in each ticker
    holdings = {ticker: 0.0 for ticker in price_data.columns}
    cash = initial_capital

    rebalance_count = 0

    # to handle auto-rebalance frequency
    current_frequency = 'none'
    next_auto_rebalance_date = None

    # Get initial settings on the first day
    first_day = all_dates[0]
    initial_settings = find_portfolio_settings_for_date(settings_history, first_day)
    if initial_settings:
        current_frequency = initial_settings.get('auto_rebalance', 'none')
        # Use helper to extract and validate ticker weights
        tickers_weights = prepare_tickers_weights(initial_settings, name, first_day)
        # Rebalance using the helper
        holdings, cash = rebalance_portfolio(
            cash, price_data.loc[first_day], tickers_weights, price_data.columns
        )

        next_auto_rebalance_date = get_next_rebalance_date(first_day, current_frequency)
        rebalance_count += 1  # initial rebalance performed

    # Initialize last applied settings date
    last_setting_applied = None
    first_day_str = first_day.strftime('%Y-%m-%d')
    if first_day_str in settings_history:
        last_setting_applied = first_day_str

    # Daily loop
    for current_day in all_dates:
        current_day_str = current_day.strftime('%Y-%m-%d')

        forced_rebalance_today = False
        if (
            current_day_str in settings_history
            and last_setting_applied != current_day_str
        ):
            forced_rebalance_today = True
            new_settings = settings_history[current_day_str]
            last_setting_applied = current_day_str  # mark as applied
            new_freq = new_settings.get('auto_rebalance', 'none')
            if new_freq != current_frequency:
                current_frequency = new_freq
                next_auto_rebalance_date = None  # recalc after rebalance

        auto_rebalance_today = (
            next_auto_rebalance_date is not None
            and current_day >= next_auto_rebalance_date
        )

        # Update portfolio value at today's close
        price_row = price_data.loc[current_day]
        portfolio_value = cash
        for t, s in holdings.items():
            px = price_row[t]
            if not np.isnan(px) and s != 0.0:
                portfolio_value += s * px
        daily_values.loc[current_day] = portfolio_value

        # Rebalance if necessary
        if forced_rebalance_today or auto_rebalance_today:
            if forced_rebalance_today:
                # Use today's explicit settings
                tickers_weights = prepare_tickers_weights(
                    new_settings, name, current_day
                )
                holdings, cash = rebalance_portfolio(
                    portfolio_value, price_row, tickers_weights, price_data.columns
                )

            elif auto_rebalance_today:
                last_settings = find_portfolio_settings_for_date(
                    settings_history, current_day
                )
                tickers_weights = prepare_tickers_weights(
                    last_settings, name, current_day
                )
                holdings, cash = rebalance_portfolio(
                    portfolio_value, price_row, tickers_weights, price_data.columns
                )

            rebalance_count += 1

            # Reschedule next auto rebalance if applicable
            if current_frequency != 'none':
                next_auto_rebalance_date = get_next_rebalance_date(
                    current_day, current_frequency
                )
            else:
                next_auto_rebalance_date = None

    return daily_values, rebalance_count
