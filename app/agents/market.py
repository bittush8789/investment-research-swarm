"""Market Agent: Collects market price data via Finance MCP and computes deterministic technical/return metrics.

Implements Section 7 of the architecture specification:
- Current Price, Volume, Market Cap, P/E, EPS, 52-week High/Low
- Calculates 1D, 1M, 6M, 1Y Return, Volatility, Maximum Drawdown, 50-Day MA, 200-Day MA using Python
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from app.mcp.client import mcp_client

logger = logging.getLogger("investment_swarm.agents.market")


class MarketAgent:
    """Agent specializing in live market telemetry and deterministic price analytics."""

    @classmethod
    def run(cls, ticker: str, period: str = "12 months") -> Dict[str, Any]:
        """Execute market data retrieval and compute return/volatility metrics."""
        logger.info("Market Agent collecting market indicators for %s", ticker)

        # 1. Fetch current price telemetry
        price_data = mcp_client.get_stock_price(ticker=ticker)
        # 2. Fetch company summary & valuation metrics
        info_data = mcp_client.get_company_info(ticker=ticker)
        # 3. Fetch 1-year historical prices for time-series calculations
        hist_data = mcp_client.get_historical_prices(ticker=ticker, period="1y")

        closes = hist_data.get("closes", [])
        dates = hist_data.get("dates", [])
        volumes = hist_data.get("volumes", [])

        # Default outputs
        curr_price = price_data.get("price")
        if curr_price is None and closes:
            curr_price = closes[-1]

        market_cap = price_data.get("market_cap") or info_data.get("market_cap")
        trailing_pe = info_data.get("trailing_pe")
        trailing_eps = info_data.get("trailing_eps")
        high_52w = price_data.get("fifty_two_week_high")
        low_52w = price_data.get("fifty_two_week_low")
        volume = price_data.get("volume") or (volumes[-1] if volumes else None)

        # Deterministic Return and Risk Calculations using Pandas / NumPy
        ret_1d: Optional[float] = price_data.get("pct_change_1d")
        ret_1m: Optional[float] = None
        ret_6m: Optional[float] = None
        ret_1y: Optional[float] = None
        volatility: Optional[float] = None
        max_drawdown: Optional[float] = None
        ma_50: Optional[float] = None
        ma_200: Optional[float] = None

        if closes and len(closes) >= 2:
            s_close = pd.Series(closes)
            n_bars = len(closes)

            # 1D Return
            if ret_1d is None:
                ret_1d = round(float((closes[-1] - closes[-2]) / closes[-2] * 100), 2)

            # 1M Return (~21 trading days)
            if n_bars >= 21:
                ret_1m = round(float((closes[-1] - closes[-21]) / closes[-21] * 100), 2)
            else:
                ret_1m = round(float((closes[-1] - closes[0]) / closes[0] * 100), 2)

            # 6M Return (~126 trading days)
            if n_bars >= 126:
                ret_6m = round(float((closes[-1] - closes[-126]) / closes[-126] * 100), 2)
            elif n_bars > 21:
                ret_6m = round(float((closes[-1] - closes[0]) / closes[0] * 100), 2)

            # 1Y Return (full year series)
            ret_1y = round(float((closes[-1] - closes[0]) / closes[0] * 100), 2)

            # 50-Day Moving Average
            if n_bars >= 50:
                ma_50 = round(float(s_close.iloc[-50:].mean()), 2)
            else:
                ma_50 = round(float(s_close.mean()), 2)

            # 200-Day Moving Average
            if n_bars >= 200:
                ma_200 = round(float(s_close.iloc[-200:].mean()), 2)
            else:
                ma_200 = round(float(s_close.mean()), 2)

            # Daily returns series
            daily_returns = s_close.pct_change().dropna()

            # Annualized Volatility: std(daily_returns) * sqrt(252) * 100
            if not daily_returns.empty:
                daily_std = float(daily_returns.std())
                volatility = round(daily_std * np.sqrt(252) * 100, 2)

            # Maximum Drawdown: Peak-to-Trough drop percentage
            cumulative_max = s_close.cummax()
            drawdowns = (s_close - cumulative_max) / cumulative_max
            max_drawdown = round(float(drawdowns.min()) * 100, 2)

        evidence: List[Dict[str, Any]] = []
        if curr_price is not None:
            evidence.append({
                "claim": f"{ticker} current trading price is ${curr_price:,.2f} with market cap of ${market_cap:,.0f}" if market_cap else f"{ticker} current price is ${curr_price:,.2f}",
                "source_type": "YFINANCE",
                "source_url": f"https://finance.yahoo.com/quote/{ticker}",
                "verified": True,
                "date": dates[-1] if dates else "Latest Trading Session",
            })

        if ret_1y is not None:
            evidence.append({
                "claim": f"{ticker} 1-year total price return calculated at {ret_1y:+.2f}% with maximum drawdown of {max_drawdown:.2f}%",
                "source_type": "QUANT",
                "source_url": "Python Deterministic Calculation",
                "verified": True,
                "date": "1-Year Period",
            })

        return {
            "status": "success",
            "ticker": ticker.upper(),
            "sector": info_data.get("sector"),
            "industry": info_data.get("industry"),
            "current_price": curr_price,
            "market_cap": market_cap,
            "trailing_pe": trailing_pe,
            "forward_pe": info_data.get("forward_pe"),
            "trailing_eps": trailing_eps,
            "fifty_two_week_high": high_52w,
            "fifty_two_week_low": low_52w,
            "volume": volume,
            "return_1d": ret_1d,
            "return_1m": ret_1m,
            "return_6m": ret_6m,
            "return_1y": ret_1y,
            "volatility": volatility,
            "max_drawdown": max_drawdown,
            "ma_50": ma_50,
            "ma_200": ma_200,
            "historical_dates": dates[-60:],  # Recent 60 trading days for frontend chart
            "historical_closes": closes[-60:],
            "evidence": evidence,
        }
