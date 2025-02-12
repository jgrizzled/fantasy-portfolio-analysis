import matplotlib.pyplot as plt
from analyze import analyze
import pandas as pd  # Added to support CSV reading

# Configuration for the analysis
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


def main(cfg):
    # Run the analysis
    try:
        results = analyze(cfg)
    except ValueError as e:
        print(f'Error: {str(e)}')
        return None

    # Print results
    print('\nBacktest Results:')
    print(
        results['stats_df'].to_string(
            index=False,
            formatters={
                'total_return': '{:.2%}'.format,
                'maxdd': '{:.2%}'.format,
                'sharpe': '{:.2f}'.format,
                'score': '{:.0f}'.format,
            },
        )
    )

    print(f'\nWinner: {results["winner"]}')

    # Plot the backtested daily equity curves for all portfolios
    plt.figure(figsize=(10, 6))
    for name in results['results_df'].columns:
        plt.plot(results['results_df'].index, results['results_df'][name], label=name)
    plt.title('Portfolio Equity Curves')
    plt.xlabel('Date')
    plt.ylabel('Portfolio Value')
    plt.legend()
    plt.tight_layout()
    plt.show()

    # New code: Read expected levels from portfolio_level.csv and build the daily equity curve
    try:
        csv_data = pd.read_csv('portfolio_level.csv')
    except Exception as e:
        print(f'Error reading portfolio_level.csv: {e}')
        return results

    # Convert the 'date' column to datetime using the format '31-Dec-24'
    csv_data['date'] = pd.to_datetime(csv_data['date'], format='%d-%b-%y')
    csv_data = csv_data.sort_values('date')
    csv_data.set_index('date', inplace=True)

    # Convert share prices into an equity curve.
    # We assume that the share price at the first date is the base to calculate total return.
    initial_level = csv_data['level'].iloc[0]
    expected_equity = (csv_data['level'] / initial_level) * cfg['initial_capital']

    # Actual equity curve from the backtest (assumed to be for the "Test Portfolio")
    actual_curve = results['results_df']['Test Portfolio']

    # Plot the daily Expected vs Actual Equity Curve
    plt.figure(figsize=(10, 6))
    plt.plot(
        actual_curve.index, actual_curve.values, label='Actual Equity Curve', marker='o'
    )
    plt.plot(
        expected_equity.index,
        expected_equity.values,
        label='Expected Equity Curve (from CSV)',
        marker='x',
        linestyle='--',
    )
    plt.title('Expected vs Actual Daily Portfolio Values')
    plt.xlabel('Date')
    plt.ylabel('Portfolio Value ($)')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # Print the last 10 dates/values for each curve
    print('\nLast 10 values of Actual Equity Curve:')
    print(actual_curve.tail(10).to_frame().to_string())

    print('\nLast 10 values of Expected Equity Curve:')
    print(expected_equity.tail(10).to_string())

    return results


if __name__ == '__main__':
    main(config)
