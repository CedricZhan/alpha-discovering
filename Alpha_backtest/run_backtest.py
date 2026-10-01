"""Monthly stock-selection backtest using the standard library, Python 3.10+."""
import argparse
import csv
import json
import math
import statistics
from datetime import date
from pathlib import Path

import Alpha

BASE = Path(__file__).resolve().parent


def load_prices(path):
    panel = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not {"date", "symbol", "adj_close"}.issubset(reader.fieldnames or []):
            raise ValueError("Data must contain date,symbol,adj_close columns.")
        for line, row in enumerate(reader, 2):
            try:
                day = date.fromisoformat(row["date"].strip())
                symbol = row["symbol"].strip()
                price = float(row["adj_close"])
                if not symbol or not math.isfinite(price) or price <= 0:
                    raise ValueError("Symbol must be nonempty and price must be finite and positive")
                values = panel.setdefault(day, {})
                if symbol in values:
                    raise ValueError("Duplicate date and symbol")
                values[symbol] = price
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError(f"Invalid data on line {line}: {exc}") from exc
    if not panel:
        raise ValueError("The data template is empty. Fill in input/prices.csv; see README.md for the format.")
    days = sorted(panel)
    symbols = sorted(set().union(*(set(v) for v in panel.values())))
    for day in days:
        missing = set(symbols) - panel[day].keys()
        if missing:
            raise ValueError(f"{day} is missing prices for: {', '.join(sorted(missing)[:10])}. Provide complete, aligned data.")
    return days, symbols, panel


def validate_config(cfg):
    for key in ("initial_cash", "top_fraction", "cost_bps", "annualization"):
        value = cfg[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Configuration value {key} must be a finite number.")
    if cfg["initial_cash"] <= 0 or not 0 < cfg["top_fraction"] <= 1:
        raise ValueError("initial_cash must be > 0 and top_fraction must be in (0,1].")
    if not 0 <= cfg["cost_bps"] < 10000 or cfg["annualization"] <= 0:
        raise ValueError("cost_bps must be in [0,10000) and annualization must be > 0.")
    start = date.fromisoformat(cfg["start_date"]) if cfg.get("start_date") else None
    end = date.fromisoformat(cfg["end_date"]) if cfg.get("end_date") else None
    if start and end and start > end:
        raise ValueError("start_date must not be later than end_date.")
    if type(Alpha.MIN_HISTORY) is not int or Alpha.MIN_HISTORY < 1:
        raise ValueError("Alpha.MIN_HISTORY must be a positive integer.")
    return start, end


def rebalance(holdings, cash, prices, targets, fee):
    """Solve for equal target values after fees charged on traded notional."""
    equity = cash + sum(qty * prices[s] for s, qty in holdings.items())
    old = {s: qty * prices[s] for s, qty in holdings.items()}
    universe = sorted(set(old) | set(targets))
    def turnover(net):
        return sum(abs((net / len(targets) if s in targets else 0) - old.get(s, 0)) for s in universe)
    low, high = 0.0, equity
    for _ in range(80):
        mid = (low + high) / 2
        if mid + fee * turnover(mid) > equity:
            high = mid
        else:
            low = mid
    net = (low + high) / 2
    new = {s: net / len(targets) / prices[s] for s in targets}
    trades = []
    for s in universe:
        delta = new.get(s, 0) - holdings.get(s, 0)
        if abs(delta * prices[s]) > 1e-8:
            trades.append({"symbol": s, "quantity": delta, "price": prices[s],
                           "notional": abs(delta * prices[s]), "cost": abs(delta * prices[s]) * fee})
    costs = sum(t["cost"] for t in trades)
    remaining_cash = equity - costs - sum(new[s] * prices[s] for s in new)
    return new, remaining_cash, trades


def backtest(days, symbols, panel, cfg):
    start, end = validate_config(cfg)
    days = [d for d in days if end is None or d <= end]
    history = {s: [] for s in symbols}
    holdings, cash, pending = {}, float(cfg["initial_cash"]), None
    previous, peak = cash, cash
    daily, trades, signals = [], [], []
    rebalances = 0
    for i, day in enumerate(days):
        prices = panel[day]
        for s in symbols:
            history[s].append(prices[s])
        if start and day < start:
            continue
        day_cost = day_turnover = 0.0
        if pending is not None:
            signal_day, targets = pending
            holdings, cash, executed = rebalance(holdings, cash, prices, targets, cfg["cost_bps"] / 10000)
            for trade in executed:
                trade.update(date=day.isoformat(), signal_date=signal_day.isoformat())
            trades.extend(executed)
            day_cost = sum(t["cost"] for t in executed)
            day_turnover = sum(t["notional"] for t in executed)
            rebalances += 1
            pending = None
        equity = cash + sum(qty * prices[s] for s, qty in holdings.items())
        peak = max(peak, equity)
        daily.append({"date": day.isoformat(), "equity": equity, "nav": equity / cfg["initial_cash"],
                      "return": equity / previous - 1, "drawdown": equity / peak - 1,
                      "cash": cash, "positions": len(holdings), "traded_notional": day_turnover, "cost": day_cost})
        previous = equity
        # Confirm month-end only when a next session exists to execute the signal.
        month_end = i + 1 < len(days) and (day.year, day.month) != (days[i + 1].year, days[i + 1].month)
        if month_end and i + 1 >= Alpha.MIN_HISTORY:
            scores = Alpha.calculate({s: tuple(values) for s, values in history.items()})
            if not isinstance(scores, dict):
                raise ValueError("Alpha.calculate must return a dict.")
            for s, score in scores.items():
                if s not in history or isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
                    raise ValueError(f"Alpha returned an invalid symbol or a non-finite score: {s}")
            ranked = sorted(scores, key=lambda s: (-scores[s], s))
            count = math.ceil(len(ranked) * cfg["top_fraction"])
            targets = ranked[:count]
            for rank, s in enumerate(ranked, 1):
                signals.append({"date": day.isoformat(), "symbol": s, "score": scores[s], "rank": rank, "selected": int(s in targets)})
            pending = (day, targets)
    if not daily:
        raise ValueError("No data in the selected backtest period.")
    if not rebalances:
        raise ValueError(f"No executable rebalance: at least {Alpha.MIN_HISTORY} sessions of history, a month-end signal and the next session are required.")
    returns = [r["return"] for r in daily]
    years = max((date.fromisoformat(daily[-1]["date"]) - date.fromisoformat(daily[0]["date"])).days / 365.25, 0)
    vol = statistics.stdev(returns) if len(returns) > 1 else 0
    summary = {"Alpha": Alpha.NAME, "start_date": daily[0]["date"], "end_date": daily[-1]["date"],
               "initial_cash": cfg["initial_cash"], "final_equity": daily[-1]["equity"],
               "total_return": daily[-1]["nav"] - 1,
               "annualized_return": daily[-1]["nav"] ** (1 / years) - 1 if years else None,
               "annualized_volatility": vol * math.sqrt(cfg["annualization"]),
               "sharpe_zero_rf": statistics.mean(returns) / vol * math.sqrt(cfg["annualization"]) if vol else None,
               "max_drawdown": min(r["drawdown"] for r in daily), "rebalance_count": rebalances,
               "total_cost": sum(t["cost"] for t in trades), "config": cfg}
    return daily, trades, signals, summary


def write_results(output, results):
    output.mkdir(parents=True, exist_ok=True)
    daily, trades, signals, summary = results
    for name, rows, fields in (
        ("daily.csv", daily, ["date", "equity", "nav", "return", "drawdown", "cash", "positions", "traded_notional", "cost"]),
        ("trades.csv", trades, ["date", "signal_date", "symbol", "quantity", "price", "notional", "cost"]),
        ("signals.csv", signals, ["date", "symbol", "score", "rank", "selected"]),
    ):
        with (output / name).open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=BASE / "config.json")
    args = parser.parse_args()
    try:
        config_path = args.config.resolve()
        cfg = json.loads(config_path.read_text(encoding="utf-8-sig"))
        validate_config(cfg)
        days, symbols, panel = load_prices(config_path.parent / cfg["data_file"])
        results = backtest(days, symbols, panel, cfg)
        output = config_path.parent / cfg["output_dir"]
        write_results(output, results)
        summary = results[-1]
        print(f"Backtest complete: {output}\nTotal return: {summary['total_return']:.2%}\nMaximum drawdown: {summary['max_drawdown']:.2%}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Backtest failed: {exc}\n")


if __name__ == "__main__":
    main()
