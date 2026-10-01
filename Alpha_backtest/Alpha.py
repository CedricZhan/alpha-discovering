"""Edit only this file to replace the Alpha; history ends on the signal date."""
from collections.abc import Mapping, Sequence

NAME = "momentum_12m_skip_1m"
MIN_HISTORY = 253  # Include today and retain the observation at t-252.


def calculate(history: Mapping[str, Sequence[float]]) -> dict[str, float]:
    """Input: symbol -> adjusted closes in date order, through today only.

    Output: symbol -> score; higher scores receive priority for selection.
    Omit symbols to exclude them; return an empty dict to move into cash.
    Change NAME, MIN_HISTORY and this function without editing other files.
    Additional inputs such as volume or fundamentals require extending the data interface.
    """
    return {
        symbol: prices[-22] / prices[-253] - 1
        for symbol, prices in history.items()
        if len(prices) >= MIN_HISTORY
    }
