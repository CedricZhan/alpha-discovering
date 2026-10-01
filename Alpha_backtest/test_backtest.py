import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import Alpha
import run_backtest as engine


class BacktestTests(unittest.TestCase):
    def config(self):
        cfg = json.loads((engine.BASE / "config.json").read_text())
        cfg.update(initial_cash=1000, cost_bps=0, top_fraction=0.5)
        return cfg

    def test_momentum_exact_offsets(self):
        prices = list(range(1, 254))
        self.assertEqual(Alpha.calculate({"A": prices})["A"], 232 / 1 - 1)
        self.assertEqual(Alpha.calculate({"A": prices[:-1]}), {})

    def test_next_close_execution_and_no_future_history(self):
        days = [date(2025, 1, 30), date(2025, 1, 31), date(2025, 2, 3), date(2025, 2, 4)]
        panel = {d: {"A": p, "B": 10} for d, p in zip(days, [10, 10, 20, 30])}
        seen = []
        def score(history):
            seen.append(history["A"])
            return {"A": 2, "B": 1}
        with patch.object(Alpha, "MIN_HISTORY", 2), patch.object(Alpha, "calculate", score):
            daily, trades, _, _ = engine.backtest(days, ["A", "B"], panel, self.config())
        self.assertEqual(seen, [(10, 10)])
        self.assertEqual(trades[0]["date"], "2025-02-03")
        self.assertAlmostEqual(daily[2]["equity"], 1000)  # Exclude the price doubling before execution.
        self.assertAlmostEqual(daily[3]["equity"], 1500)

    def test_cost_and_cash_conservation(self):
        holdings, cash, trades = engine.rebalance({}, 1000, {"A": 10}, ["A"], 0.01)
        self.assertAlmostEqual(holdings["A"] * 10, 1000 / 1.01)
        self.assertAlmostEqual(cash, 0)
        self.assertAlmostEqual(holdings["A"] * 10 + trades[0]["cost"], 1000)
        new, cash, sales = engine.rebalance(holdings, cash, {"A": 20}, [], 0.01)
        self.assertEqual(new, {})
        self.assertAlmostEqual(cash, holdings["A"] * 20 * 0.99)
        self.assertLess(sales[0]["quantity"], 0)

    def test_holdings_drift_without_daily_rebalance(self):
        holdings, cash, _ = engine.rebalance({}, 1000, {"A": 10, "B": 10}, ["A", "B"], 0)
        self.assertEqual(holdings, {"A": 50, "B": 50})
        self.assertAlmostEqual(sum(holdings[s] * p for s, p in {"A": 20, "B": 10}.items()) + cash, 1500)
        new, _, _ = engine.rebalance(holdings, cash, {"A": 20, "B": 10}, ["A", "B"], 0)
        self.assertEqual(new, {"A": 37.5, "B": 75})

    def test_invalid_input(self):
        for body in ("", "2025-01-01,A,1\n2025-01-01,A,2\n",
                     "2025-01-01,A,nan\n", "2025-01-01,A,1\n2025-01-02,B,2\n"):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "prices.csv"
                path.write_text("date,symbol,adj_close\n" + body)
                with self.assertRaises(ValueError):
                    engine.load_prices(path)

    def test_full_pipeline_with_synthetic_data(self):
        from datetime import timedelta
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prices.csv"
            day = date(2023, 1, 2)
            with path.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["date", "symbol", "adj_close"])
                for i in range(600):
                    day += timedelta(days=1)
                    if day.weekday() < 5:
                        writer.writerow([day, "A", 100 * 1.001 ** i])
                        writer.writerow([day, "B", 100])
            results = engine.backtest(*engine.load_prices(path), self.config())
            engine.write_results(Path(tmp) / "output", results)
            self.assertGreater(results[-1]["total_return"], 0)
            self.assertTrue(all(t["date"] > t["signal_date"] for t in results[1]))
            self.assertEqual(len(list((Path(tmp) / "output").iterdir())), 4)


if __name__ == "__main__":
    unittest.main()
