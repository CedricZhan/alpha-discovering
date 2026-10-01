# Alpha Discovering

**A lightweight Python workspace for researching and backtesting stock-selection Alphas.**

Supply daily adjusted prices, define an Alpha in one file, and inspect portfolio returns, trading costs, and selection decisions. The current engine runs locally using the Python standard library.

## What you can do

- Replace a price-based Alpha by editing only `Alpha_backtest/Alpha.py`.
- Rank stocks monthly and build an equal-weight, long-only portfolio.
- Execute signals at the next trading session's close, with configurable transaction costs.
- Export daily performance, trades, Alpha rankings, and summary statistics.

The included Alpha is 12-month momentum excluding the latest month. The input CSV is intentionally empty: provide your own market data before running a backtest.

## Quick start

Requires **Python 3.10+**. Run the following commands from the repository root.

### 1. Prepare Python

On Windows:

```powershell
python -m venv .venv
```

Skip this step if `.venv` already exists. The backtest requires no third-party packages; the root `requirements.txt` is not needed to run it.

### 2. Add your data

Fill in [`Alpha_backtest/input/prices.csv`](Alpha_backtest/input/prices.csv):

```csv
date,symbol,adj_close
2024-01-02,AAA,100.00
2024-01-02,BBB,50.00
2024-01-03,AAA,101.00
2024-01-03,BBB,49.50
```

These rows illustrate the format only.

| Column | Description |
| --- | --- |
| `date` | Trading date in `YYYY-MM-DD` format |
| `symbol` | Stock identifier, read as text |
| `adj_close` | Finite, positive adjusted closing price |

Use consistent adjustment and currency conventions. Every date must contain every stock; duplicate rows and missing prices are rejected. Ensure the market calendar is complete, as dates missing for all stocks cannot be detected.

The default Alpha needs **253 trading sessions of history**, then a qualifying month-end and the next session to execute. Supply at least two years of data for a more useful research window.

### 3. Run the backtest

```powershell
.\.venv\Scripts\python.exe .\Alpha_backtest\run_backtest.py
```

On macOS or Linux, use `python3 Alpha_backtest/run_backtest.py` with Python 3.10+ installed.

Results are written to `Alpha_backtest/output/`. An empty input produces an explanatory error. Each successful run overwrites the four result files in the configured output directory.

## Define your Alpha

Edit [`Alpha_backtest/Alpha.py`](Alpha_backtest/Alpha.py). Its contract is:

| Member | Purpose |
| --- | --- |
| `NAME` | Alpha identifier recorded in the results |
| `MIN_HISTORY` | Minimum number of historical observations required |
| `calculate(history)` | Return a dictionary mapping symbols to numeric scores |

`history` maps each symbol to an immutable sequence of adjusted closes, oldest first, ending on the signal date. Higher scores rank first. Omitted symbols are excluded; an empty dictionary moves the portfolio into cash at the next execution.

The included momentum signal is:

```python
prices[-22] / prices[-253] - 1
```

This corresponds to `P(t-21) / P(t-252) - 1`, using trading-session offsets.

The one-file replacement interface supports price-based Alphas. Volume, fundamental, or industry inputs require extending the data interface first. See the [engine guide](Alpha_backtest/README.md) for a complete replacement example.

## Configure the strategy

Edit [`Alpha_backtest/config.json`](Alpha_backtest/config.json):

| Setting | Default | Meaning |
| --- | --- | --- |
| `initial_cash` | `1000000` | Starting capital |
| `top_fraction` | `0.2` | Buy the top 20% of ranked stocks, rounding the count up |
| `cost_bps` | `10` | Charge 0.1% of each buy or sell's traded notional |
| `start_date`, `end_date` | `null` | Optional inclusive date bounds |
| `annualization` | `252` | Sessions per year for volatility and Sharpe calculations |
| `data_file` | `input/prices.csv` | Input CSV path |
| `output_dir` | `output` | Results directory |

Input and output paths are relative to the configuration file. Use `--config PATH` to load another configuration.

## How the simulation works

1. Accumulate price history and calculate Alpha scores after each qualifying month-end close.
2. Select the highest-scoring stocks; break ties by symbol.
3. Rebalance at the next session's close into equal positions after costs.
4. Keep share quantities unchanged between rebalances and mark holdings to market daily.

New positions do not earn returns before execution. Existing positions remain exposed until they are traded. Cash earns no interest, fractional shares are allowed, and the final portfolio is valued without forced liquidation.

Data before `start_date` is available for warm-up but generates no signals. Without a start date, performance includes the initial cash-only warm-up period.

## Inspect the results

| File | Contents |
| --- | --- |
| `daily.csv` | Equity, NAV, returns, drawdowns, cash, position counts, turnover amounts, and costs |
| `trades.csv` | Signal and execution dates, symbols, quantity changes, simulated prices, and costs |
| `signals.csv` | Alpha scores, rankings, and selection flags |
| `summary.json` | Alpha name, configuration, total and annualized returns, volatility, Sharpe, maximum drawdown, and total costs |

Returns are stored as decimals: `0.10` means 10%. Drawdowns are negative. Sharpe assumes a zero risk-free rate and is `null` for zero volatility. Annualized return uses elapsed calendar time; volatility and Sharpe use the configured trading-session count.

## Project layout

```text
Alpha_backtest/
    Alpha.py           # Replaceable Alpha definition
    run_backtest.py    # Data validation, simulation, and reporting
    config.json        # Strategy and path settings
    input/prices.csv   # Empty market-data template
    test_backtest.py   # Automated validation
    README.md          # Detailed engine guide
    output/            # Generated after a successful run
```

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s .\Alpha_backtest -p "test_*.py" -v
```

The six tests cover momentum offsets, signal timing, next-close execution, fees and cash conservation, holding drift, invalid input, and end-to-end reporting. Synthetic test data stays in temporary directories; your input template remains unchanged.

## Scope and limitations

The engine currently assumes a fixed universe with complete daily prices. It does not model suspensions, price limits, liquidity constraints, board lots, changing constituents, or separate tax schedules. Adjusted prices and quantities are simulation values, not actual trade fills.

Historical universe selection and data quality remain the researcher's responsibility. Using only surviving stocks introduces survivorship bias. Use total-return adjusted prices if returns should include cash dividends.

Benchmark comparisons, IC analysis, grouped portfolios, industry/size neutralization, market-data downloads, and broker execution are not implemented in this engine.
