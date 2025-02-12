import numpy as np


def compute_max_drawdown(equity_curve):
    """
    Compute the maximum drawdown from a series of portfolio values.
    """
    peak = equity_curve.expanding(min_periods=1).max()
    drawdown = (equity_curve - peak) / peak
    max_dd = drawdown.min()
    return max_dd  # typically negative, e.g. -0.20 means -20%


def compute_sharpe_ratio(equity_curve, periods_per_year=252):
    """
    Compute a simple annualized Sharpe ratio from daily equity values:
    SR = mean(daily_returns)/std(daily_returns) * sqrt(periods_per_year).
    """
    daily_returns = equity_curve.pct_change().dropna()
    if daily_returns.std() == 0:
        return 0.0
    return daily_returns.mean() / daily_returns.std() * np.sqrt(periods_per_year)
