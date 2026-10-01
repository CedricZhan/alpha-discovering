# Alpha Discovering

Python project for quantitative factor research and Interactive Brokers TWS integration.

## IBKR TWS connection

The initial connection checker uses the official `ibapi` package and defaults
to TWS at `127.0.0.1:7496`.

Before running it, open TWS and enable **API > Settings > Enable ActiveX and
Socket Clients**. For research-only use, enable the TWS **Read-Only API**
setting as well.

```powershell
.\.venv\Scripts\python.exe .\ibkr_connection.py
```

Use a different client ID when another API program is already connected:

```powershell
.\.venv\Scripts\python.exe .\ibkr_connection.py --client-id 2
```

The script only performs the API handshake, reads managed account identifiers,
and requests the IBKR server time. It does not submit orders.

## Local NVDA data report

With TWS running, fetch one year of NVDA daily bars and build a fully local
CSV dataset and Markdown report:

```powershell
.\.venv\Scripts\python.exe .\nvda_report.py
```

Outputs are written to `data/market/` and `reports/`. The data comes through
the local TWS socket; the script does not call a web market-data provider.

## Status

Initial repository setup.
