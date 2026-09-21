"""Finance MCP Server using yfinance for market, valuation, and financial statement data.

Implements tools specified in Section 16 of the architecture specification:
- get_stock_price
- get_historical_prices
- get_company_info
- get_financials
- get_balance_sheet
- get_cashflow
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import yfinance as yf
import pandas as pd
import numpy as np

logger = logging.getLogger("investment_swarm.mcp.finance")


class FinanceMCPServer:
    """Finance MCP Server exposing yfinance market tools."""

    @staticmethod
    def get_stock_price(ticker: str) -> Dict[str, Any]:
        """Retrieve current real-time or latest market price, volume, and day range."""
        try:
            ticker_obj = yf.Ticker(ticker.strip().upper())
            fast_info = ticker_obj.fast_info

            # Fallback to info dict if fast_info is sparse
            price = getattr(fast_info, "last_price", None)
            prev_close = getattr(fast_info, "previous_close", None)
            market_cap = getattr(fast_info, "market_cap", None)
            volume = getattr(fast_info, "last_volume", None)
            high_52w = getattr(fast_info, "year_high", None)
            low_52w = getattr(fast_info, "year_low", None)

            if price is None:
                info = ticker_obj.info or {}
                price = info.get("currentPrice") or info.get("regularMarketPrice")
                prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
                market_cap = info.get("marketCap")
                volume = info.get("volume") or info.get("regularMarketVolume")
                high_52w = info.get("fiftyTwoWeekHigh")
                low_52w = info.get("fiftyTwoWeekLow")

            change_1d = None
            pct_change_1d = None
            if price is not None and prev_close is not None and prev_close > 0:
                change_1d = round(price - prev_close, 2)
                pct_change_1d = round(((price - prev_close) / prev_close) * 100, 2)

            return {
                "status": "success",
                "ticker": ticker.upper(),
                "price": round(float(price), 2) if price else None,
                "previous_close": round(float(prev_close), 2) if prev_close else None,
                "change_1d": change_1d,
                "pct_change_1d": pct_change_1d,
                "market_cap": float(market_cap) if market_cap else None,
                "volume": int(volume) if volume else None,
                "fifty_two_week_high": round(float(high_52w), 2) if high_52w else None,
                "fifty_two_week_low": round(float(low_52w), 2) if low_52w else None,
            }
        except Exception as exc:
            logger.error("Error retrieving stock price for %s: %s", ticker, exc)
            return {"status": "error", "ticker": ticker, "error": str(exc)}

    @staticmethod
    def get_historical_prices(ticker: str, period: str = "1y") -> Dict[str, Any]:
        """Retrieve daily historical closing prices, volumes, and date indexes."""
        try:
            # Map friendly period names
            period_map = {
                "12 months": "1y",
                "1 year": "1y",
                "6 months": "6mo",
                "1 month": "1mo",
                "3 months": "3mo",
                "2 years": "2y",
                "5 years": "5y",
            }
            yf_period = period_map.get(period.lower(), period)

            ticker_obj = yf.Ticker(ticker.strip().upper())
            hist = ticker_obj.history(period=yf_period)

            if hist.empty:
                return {
                    "status": "error",
                    "ticker": ticker.upper(),
                    "error": f"No historical price data found for period '{period}'",
                }

            # Extract dates, closes, volumes
            dates = [d.strftime("%Y-%m-%d") for d in hist.index]
            closes = [round(float(c), 2) for c in hist["Close"]]
            volumes = [int(v) for v in hist["Volume"]]
            highs = [round(float(h), 2) for h in hist["High"]]
            lows = [round(float(l), 2) for l in hist["Low"]]

            return {
                "status": "success",
                "ticker": ticker.upper(),
                "period": yf_period,
                "count": len(dates),
                "start_date": dates[0] if dates else None,
                "end_date": dates[-1] if dates else None,
                "dates": dates,
                "closes": closes,
                "highs": highs,
                "lows": lows,
                "volumes": volumes,
            }
        except Exception as exc:
            logger.error("Error retrieving historical prices for %s: %s", ticker, exc)
            return {"status": "error", "ticker": ticker, "error": str(exc)}

    @staticmethod
    def get_company_info(ticker: str) -> Dict[str, Any]:
        """Retrieve company background, sector, industry, description, and summary ratios."""
        try:
            ticker_obj = yf.Ticker(ticker.strip().upper())
            info = ticker_obj.info or {}

            return {
                "status": "success",
                "ticker": ticker.upper(),
                "name": info.get("longName") or info.get("shortName") or ticker.upper(),
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "summary": info.get("longBusinessSummary", "No company summary available."),
                "website": info.get("website", ""),
                "employees": info.get("fullTimeEmployees"),
                "country": info.get("country", "United States"),
                "exchange": info.get("exchange", "NASDAQ"),
                "trailing_pe": round(float(info["trailingPE"]), 2) if "trailingPE" in info and info["trailingPE"] else None,
                "forward_pe": round(float(info["forwardPE"]), 2) if "forwardPE" in info and info["forwardPE"] else None,
                "price_to_book": round(float(info["priceToBook"]), 2) if "priceToBook" in info and info["priceToBook"] else None,
                "trailing_eps": round(float(info["trailingEps"]), 2) if "trailingEps" in info and info["trailingEps"] else None,
                "forward_eps": round(float(info["forwardEps"]), 2) if "forwardEps" in info and info["forwardEps"] else None,
                "dividend_yield": round(float(info["dividendYield"]) * 100, 2) if "dividendYield" in info and info["dividendYield"] else None,
                "beta": round(float(info["beta"]), 2) if "beta" in info and info["beta"] else None,
            }
        except Exception as exc:
            logger.error("Error retrieving company info for %s: %s", ticker, exc)
            return {"status": "error", "ticker": ticker, "error": str(exc)}

    @staticmethod
    def get_financials(ticker: str) -> Dict[str, Any]:
        """Retrieve recent income statement items (Revenue, Net Income, Gross Profit, Operating Income)."""
        try:
            ticker_obj = yf.Ticker(ticker.strip().upper())
            fin = ticker_obj.financials

            if fin is None or fin.empty:
                return {"status": "not_available", "ticker": ticker.upper(), "data": {}}

            # Convert to dictionary with string dates
            data: Dict[str, Dict[str, Optional[float]]] = {}
            for col in fin.columns:
                date_str = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
                data[date_str] = {}
                for idx, val in fin[col].items():
                    if pd.notna(val):
                        data[date_str][str(idx)] = float(val)

            return {
                "status": "success",
                "ticker": ticker.upper(),
                "financials": data,
            }
        except Exception as exc:
            logger.error("Error retrieving financials for %s: %s", ticker, exc)
            return {"status": "error", "ticker": ticker, "error": str(exc)}

    @staticmethod
    def get_balance_sheet(ticker: str) -> Dict[str, Any]:
        """Retrieve balance sheet items (Cash, Debt, Assets, Liabilities, Equity)."""
        try:
            ticker_obj = yf.Ticker(ticker.strip().upper())
            bs = ticker_obj.balance_sheet

            if bs is None or bs.empty:
                return {"status": "not_available", "ticker": ticker.upper(), "data": {}}

            data: Dict[str, Dict[str, Optional[float]]] = {}
            for col in bs.columns:
                date_str = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
                data[date_str] = {}
                for idx, val in bs[col].items():
                    if pd.notna(val):
                        data[date_str][str(idx)] = float(val)

            return {
                "status": "success",
                "ticker": ticker.upper(),
                "balance_sheet": data,
            }
        except Exception as exc:
            logger.error("Error retrieving balance sheet for %s: %s", ticker, exc)
            return {"status": "error", "ticker": ticker, "error": str(exc)}

    @staticmethod
    def get_cashflow(ticker: str) -> Dict[str, Any]:
        """Retrieve cash flow statement items (Operating Cash Flow, CapEx, Free Cash Flow)."""
        try:
            ticker_obj = yf.Ticker(ticker.strip().upper())
            cf = ticker_obj.cashflow

            if cf is None or cf.empty:
                return {"status": "not_available", "ticker": ticker.upper(), "data": {}}

            data: Dict[str, Dict[str, Optional[float]]] = {}
            for col in cf.columns:
                date_str = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
                data[date_str] = {}
                for idx, val in cf[col].items():
                    if pd.notna(val):
                        data[date_str][str(idx)] = float(val)

            return {
                "status": "success",
                "ticker": ticker.upper(),
                "cashflow": data,
            }
        except Exception as exc:
            logger.error("Error retrieving cashflow for %s: %s", ticker, exc)
            return {"status": "error", "ticker": ticker, "error": str(exc)}
