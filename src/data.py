import pandas as pd
import yfinance as yf
from requests.adapters import HTTPAdapter
from requests import Session
from requests.packages import urllib3
from datetime import datetime, timedelta
import sqlite3
from zoneinfo import ZoneInfo

urllib3.disable_warnings()

PRICE_CACHE_FILE = 'price_cache.sqlite'
NY_TZ = ZoneInfo('America/New_York')


def initdb():
    conn = sqlite3.connect(PRICE_CACHE_FILE)
    cur = conn.cursor()
    # Define migrations as a list of SQL migration scripts. Each element represents a schema upgrade.
    migrations = [
        # Migration 1: Create tables
        """
        CREATE TABLE IF NOT EXISTS fetches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            start INT,
            end INT,
            UNIQUE(ticker, start, end)
        );
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            date INT,
            close REAL,
            UNIQUE(ticker, date) 
        );
        -- Indexes on ticker
        CREATE INDEX IF NOT EXISTS idx_fetches_ticker ON fetches(ticker);
        CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices(ticker);
        -- SQLite Settings
        PRAGMA journal_mode = wal;
		PRAGMA synchronous = normal;
		PRAGMA analysis_limit = 1000;
        """
    ]
    # Get the current schema version
    cur.execute('PRAGMA user_version')
    current_version = cur.fetchone()[0]
    total_migrations = len(migrations)
    # Apply pending migrations
    for i in range(current_version, total_migrations):
        cur.executescript(migrations[i])
        cur.execute(f'PRAGMA user_version = {i + 1}')
        conn.commit()
    conn.execute('PRAGMA optimize')
    return conn


def get_price_data(
    tickers: list[str], start_date: datetime, end_date: datetime
) -> pd.DataFrame:
    """
    Gets price data for the given tickers and date range,
    using a local SQLite price cache or yfinance.

    The cache records each fetch in the 'fetches' table with ticker, start, end (as integer timestamps)
    and stores the price data in the 'prices' table with ticker, date (as integer timestamp), and close.
    If a cached fetch fully covers the requested range for a ticker, data is loaded from the cache.
    Otherwise, the full range is downloaded from yfinance, stored in the cache, and then used.

    Args:
        tickers (list): List of ticker symbols
        start_date (datetime): Start date for data download
        end_date (datetime): End date for data download

    Returns:
        DataFrame: Processed daily price data with tickers as columns.
    """
    # Ensure end_date is not in the future or today, else set it to yesterday
    now = datetime.now()
    yesterday = datetime(now.year, now.month, now.day) - pd.Timedelta(days=1)
    if end_date >= yesterday:
        end_date = yesterday

    # Convert requested dates to integer timestamps (seconds since epoch)
    # Adjust start date to previous day to ensure we catch NY market open
    start_date_ny = start_date.astimezone(NY_TZ)
    start_date_ny = start_date_ny.replace(hour=0, minute=0, second=0, microsecond=0)
    start_date_ny = start_date_ny - timedelta(days=1)

    end_date_ny = end_date.astimezone(NY_TZ)
    end_date_ny = end_date_ny.replace(hour=0, minute=0, second=0, microsecond=0)

    req_start_int = int(start_date_ny.timestamp())
    req_end_int = int(end_date_ny.timestamp())

    # Initialize (or create) the sqlite cache database with migrations applied
    conn = initdb()
    cur = conn.cursor()

    cached_data = {}
    missing_tickers = []

    # Check the cache for each ticker
    for ticker in tickers:
        cur.execute(
            'SELECT start, end FROM fetches WHERE ticker=? AND start<=? AND end>=? LIMIT 1',
            (ticker, req_start_int, req_end_int),
        )
        row = cur.fetchone()
        if row is not None:
            # Cached fetch exists, load the cached prices for this ticker
            cur.execute(
                'SELECT date, close FROM prices WHERE ticker=? AND date >= ? AND date < ? ORDER BY date ASC',
                (ticker, req_start_int, req_end_int),
            )
            rows = cur.fetchall()
            if rows:
                dates = [pd.to_datetime(r[0], unit='s') for r in rows]
                close_vals = [r[1] for r in rows]
                cached_data[ticker] = pd.Series(close_vals, index=dates)
            else:
                missing_tickers.append(ticker)
        else:
            missing_tickers.append(ticker)

    # For tickers not fully cached, download from yfinance
    if missing_tickers:
        session = Session()
        session.mount('https://', HTTPAdapter(max_retries=3))
        fetched = yf.download(
            missing_tickers if len(missing_tickers) > 1 else missing_tickers[0],
            start=start_date,
            end=end_date,
            progress=False,
            timeout=30,
            session=session,
            threads=False,
            auto_adjust=True,
        )
        data = fetched['Close']
        # If only one ticker was requested, ensure it is a DataFrame
        if isinstance(data, pd.Series):
            data = data.to_frame()
        # Cache the fetched data for each missing ticker
        for ticker in missing_tickers:
            if ticker not in data.columns:
                continue
            ticker_series = data[ticker].dropna()
            # Record the fetch in the fetches table
            cur.execute(
                'INSERT INTO fetches (ticker, start, end) VALUES (?, ?, ?)',
                (ticker, req_start_int, req_end_int),
            )
            # Insert each price point into the prices table
            for dt, price in ticker_series.items():
                dt_ny = dt.tz_localize('UTC').astimezone(NY_TZ)
                dt_int = int(dt_ny.timestamp())
                cur.execute(
                    'INSERT OR IGNORE INTO prices (ticker, date, close) VALUES (?, ?, ?)',
                    (ticker, dt_int, float(price)),
                )
            conn.commit()
            cached_data[ticker] = ticker_series

    # Combine the price data for all tickers into one DataFrame
    series_list = []
    for ticker in tickers:
        if ticker in cached_data:
            s = cached_data[ticker].copy()
            s.name = ticker
            series_list.append(s)

    if series_list:
        combined_data = pd.concat(series_list, axis=1).sort_index().ffill()
    else:
        combined_data = pd.DataFrame()

    conn.close()
    return combined_data
