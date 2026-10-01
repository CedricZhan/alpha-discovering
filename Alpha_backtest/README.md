# Replaceable Alpha backtest

Requires Python 3.10 or newer. Uses only the standard library; no additional packages are required.
The framework ranks stocks at month-end, trades at the next session's close, and holds the highest-scoring stocks in a long-only portfolio.

## 1. Supply data

`input/prices.csv` contains only a header, with no real or simulated observations. Fill it using this format:

```csv
date,symbol,adj_close
2024-01-02,AAA,10.00
2024-01-02,BBB,20.00
2024-01-03,AAA,10.10
2024-01-03,BBB,19.90
```

These rows illustrate the format only; they are not a usable backtest dataset.

| Column | Requirement |
| --- | --- |
| date | Trading date in YYYY-MM-DD format |
| symbol | Stock identifier, read as text to preserve leading zeros |
| adj_close | Finite, positive adjusted close; use consistent adjustment and currency conventions |

Each row represents one stock on one date. Duplicate date/symbol pairs are rejected. Rows are sorted by date automatically.
Supply a complete, aligned price panel for a single market calendar: every date must include every stock.
Missing, duplicate or nonpositive prices raise errors; the program never fills missing prices automatically.
Dates omitted for every stock cannot be detected, so verify calendar completeness yourself.

The default Alpha needs at least 253 sessions of history, followed by a qualifying month-end and a next session for execution. Two or more years of data are recommended.
Data before `start_date` is used for warm-up but does not generate signals. The first trade occurs after a qualifying month-end on or after the start date.
Without `start_date`, reporting begins on the first data date. The portfolio holds cash during warm-up, and statistics include that period.

## 2. Run

From the project root:

```powershell
.\.venv\Scripts\python.exe .\Alpha_backtest\run_backtest.py
```

With your own Python installation:

```powershell
python .\Alpha_backtest\run_backtest.py
```

Default configuration and data paths are resolved from this framework's directory, independently of the working directory.
Use `--config PATH` to select another JSON file; input and output paths are resolved relative to that configuration file.
An empty template produces an explanatory error and no fabricated results. A successful run overwrites the four result files in the configured output directory.

## 3. Replace the Alpha by editing Alpha.py only

`calculate(history)` receives `symbol -> adjusted close sequence`, ordered oldest to newest through the signal date.
Each sequence is an immutable tuple containing no future observations. Return `symbol -> finite numeric score`; higher scores receive priority for selection.
Omitted symbols are excluded from the current ranking. An empty dictionary liquidates holdings at the next session's close.

The current Alpha computes `prices[-22] / prices[-253] - 1`, or `P(t-21)/P(t-252)-1`.
For a 20-session reversal signal, replace **Alpha.py** with:

```python
NAME = "reversal_20d"
MIN_HISTORY = 21

def calculate(history):
    return {
        symbol: -(prices[-1] / prices[-21] - 1)
        for symbol, prices in history.items()
        if len(prices) >= MIN_HISTORY
    }
```

The single-file interface supports Alphas computed from existing price data, including helper functions and cross-sectional calculations in the same file.
Volume, fundamentals and industry data are not included; those inputs require extending the data format and loader first.

## 4. Configuration

Edit `config.json` without changing the engine:

| Setting | Default | Meaning |
| --- | --- | --- |
| initial_cash | 1000000 | Initial capital |
| top_fraction | 0.2 | Select the top 20%; round the stock count upward |
| cost_bps | 10 | Cost on each buy or sell's notional; 10 means 0.1%, and may include assumed fees and slippage |
| start_date / end_date | null | Optional inclusive YYYY-MM-DD bounds |
| annualization | 252 | Sessions per year for volatility and Sharpe calculations |
| data_file / output_dir | See config | Input and output locations |

Ties are broken by symbol for reproducibility. Month-end is the last supplied session before a calendar-month change.
Signals are computed after that close and executed at the next close. New holdings do not earn the return between the signal close and execution close; existing holdings remain exposed during that interval.
Each rebalance targets equal values after costs, with fees charged on traded notional. Share quantities remain constant between rebalances.
Fractional shares and adjusted prices simulate returns; reported quantities and prices are research values, not actual order sizes or raw execution prices.
Final holdings are marked to market without forced liquidation or hypothetical closing sale fees. Cash earns no interest.

## 5. Outputs

- `output/daily.csv`: daily equity, NAV, return, drawdown, cash, position count, traded notional and costs.
- `output/trades.csv`: signal date, execution date, symbol, quantity change, simulated price, notional and costs. Positive quantities are buys; negative quantities are sells.
- `output/signals.csv`: Alpha scores, ranks and selection flags for each signal date.
- `output/summary.json`: Alpha name under the `Alpha` key, total return, calendar-time annualized return, annualized volatility, zero-risk-free-rate Sharpe, maximum drawdown and configuration.

Returns in CSV/JSON are decimals: 0.1 means 10%. Drawdown is negative. Sharpe is null when volatility is zero.
This is a single-portfolio backtest; benchmark excess returns, IC, grouped portfolio analysis and industry/size neutralization are not implemented.

## 6. Limitations and validation

This version supports basic research on complete price panels. It does not model suspensions, price limits, volume constraints, board lots, separate tax schedules or actual fills.
Do not forward-fill suspended stocks and treat those prices as executable. Listings, delistings and changing historical universes require extending the universe and trading-status models.
Using only currently surviving stocks introduces survivorship bias; the engine cannot repair biases in supplied data.
Use total-return adjusted prices to include cash dividends; otherwise returns may not reflect all distributions.

Run validation from the project root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s .\Alpha_backtest -p "test_*.py" -v
```

Tests generate synthetic data only in temporary directories and leave the input template empty.
They cover momentum offsets, signal information boundaries, next-close execution, trading costs, cash conservation, holding drift, invalid inputs and end-to-end output generation.
