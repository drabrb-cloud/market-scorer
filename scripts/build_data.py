#!/usr/bin/env python3
"""
Market Context Scorer - Data Builder
Scarica dati da Yahoo Finance e genera JSON per la dashboard.
Eseguito automaticamente da GitHub Actions ogni giorno.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import sys
from datetime import datetime, timedelta

# ── CONFIGURAZIONE ──

PORTFOLIO_VALUE = 1_611_327

# Indici principali
MARKET_TICKERS = {
    "QQQ": "Nasdaq 100",
    "SPY": "S&P 500",
    "DIA": "Dow Jones",
    "IWM": "Russell 2000",
}

# ETF settoriali
SECTOR_TICKERS = {
    "SMH": "Semiconduttori",
    "XLK": "Technology",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLI": "Industrials",
    "XLV": "Healthcare",
    "XLC": "Communication",
    "XLY": "Consumer Discr.",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "ARKK": "Innovation",
    "IBB": "Biotech",
    "XME": "Metals & Mining",
    "HACK": "Cybersecurity",
    "TAN": "Solar",
    "BITQ": "Crypto/Blockchain",
    "ITB": "Homebuilders",
    "KRE": "Regional Banks",
}

# Universo per breadth (top 80 S&P 500 per rappresentativita)
BREADTH_UNIVERSE = [
    "AAPL","MSFT","NVDA","GOOG","META","AVGO","ADBE","CRM","AMD","INTC",
    "ORCL","CSCO","NOW","QCOM","AMAT","MU","LRCX","KLAC","SNPS","CDNS",
    "UNH","JNJ","LLY","PFE","ABBV","MRK","TMO","ABT","DHR","AMGN",
    "JPM","V","MA","BAC","WFC","GS","MS","BLK","SCHW","AXP",
    "AMZN","TSLA","HD","MCD","NKE","SBUX","TJX","LOW","BKNG","CMG",
    "CAT","UNP","HON","BA","RTX","DE","LMT","GE","MMM","FDX",
    "XOM","CVX","COP","SLB","EOG","MPC","PSX","VLO","OXY","HES",
    "NFLX","DIS","CMCSA","T","VZ","TMUS","CHTR","EA","TTWO","WBD",
]


def download_safe(tickers, period="6mo", interval="1d"):
    """Download con gestione errori."""
    try:
        if isinstance(tickers, list):
            tickers = " ".join(tickers)
        df = yf.download(tickers, period=period, interval=interval, progress=False, auto_adjust=True, threads=True)
        return df
    except Exception as e:
        print(f"  ERRORE download {tickers}: {e}", file=sys.stderr)
        return None


def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def calc_sma(series, period):
    return series.rolling(window=period).mean()


def get_ticker_close(data, ticker):
    """Estrai close per un ticker da dati multi o singoli."""
    if isinstance(data.columns, pd.MultiIndex):
        if ticker in data.columns.get_level_values(1):
            return data["Close"][ticker].dropna()
        return None
    else:
        return data["Close"].dropna()


def analyze_index(data, ticker):
    """Analisi completa di un indice/ETF."""
    close = get_ticker_close(data, ticker)
    if close is None or len(close) < 50:
        return None

    last = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) >= 2 else last

    ema21 = calc_ema(close, 21)
    ema50 = calc_ema(close, 50)
    sma200 = calc_sma(close, 200)

    last_ema21 = float(ema21.iloc[-1])
    last_ema50 = float(ema50.iloc[-1])
    last_sma200 = float(sma200.iloc[-1]) if not pd.isna(sma200.iloc[-1]) else 0

    # Slope EMA21 (5 giorni)
    ema21_5ago = float(ema21.iloc[-5]) if len(ema21) >= 5 else float(ema21.iloc[0])
    ema21_slope = (last_ema21 - ema21_5ago) / ema21_5ago * 100

    # Performance
    ret_1d = (last / prev - 1) * 100 if prev > 0 else 0
    ret_1w = (last / float(close.iloc[-5]) - 1) * 100 if len(close) >= 5 else 0
    ret_4w = (last / float(close.iloc[-20]) - 1) * 100 if len(close) >= 20 else 0

    # Higher highs / higher lows
    hh_hl = True
    if len(close) >= 20:
        recent = close.tail(20)
        weekly_highs = []
        weekly_lows = []
        for i in range(0, 20, 5):
            chunk = recent.iloc[i:i+5]
            if len(chunk) > 0:
                weekly_highs.append(float(chunk.max()))
                weekly_lows.append(float(chunk.min()))
        if len(weekly_highs) >= 3:
            hh = sum(1 for i in range(1, len(weekly_highs)) if weekly_highs[i] >= weekly_highs[i-1])
            hl = sum(1 for i in range(1, len(weekly_lows)) if weekly_lows[i] >= weekly_lows[i-1])
            hh_hl = (hh + hl) >= 2

    # Sparkline data (ultimi 30 giorni)
    spark = [float(x) for x in close.tail(30).values]

    above_ema21 = last > last_ema21
    ema_aligned = last_ema21 > last_ema50
    above_sma200 = last > last_sma200 if last_sma200 > 0 else True

    return {
        "price": round(last, 2),
        "change_1d": round(ret_1d, 2),
        "change_1w": round(ret_1w, 2),
        "change_4w": round(ret_4w, 2),
        "ema21": round(last_ema21, 2),
        "ema50": round(last_ema50, 2),
        "sma200": round(last_sma200, 2),
        "dist_ema21_pct": round((last - last_ema21) / last_ema21 * 100, 2),
        "ema21_slope": round(ema21_slope, 3),
        "above_ema21": above_ema21,
        "ema_aligned": ema_aligned,
        "above_sma200": above_sma200,
        "hh_hl": hh_hl,
        "sparkline": spark,
    }


def calc_trend_score(analysis):
    """Score per A1 - Trend (0-1)."""
    if analysis is None:
        return 0
    score = 0
    if analysis["above_ema21"] and analysis["ema21_slope"] > 0:
        score += 1
    elif analysis["above_ema21"]:
        score += 0.5
    if analysis["ema_aligned"]:
        score += 0.5
    if analysis["above_sma200"]:
        score += 0.25
    if analysis["hh_hl"]:
        score += 0.25
    return min(score / 2.0, 1.0)


def calc_breadth(data):
    """Calcola market breadth."""
    above_50 = 0
    total = 0
    advancing = 0
    declining = 0
    near_highs = 0
    near_lows = 0

    for ticker in BREADTH_UNIVERSE:
        try:
            close = get_ticker_close(data, ticker)
            if close is None or len(close) < 50:
                continue

            last = float(close.iloc[-1])
            sma50 = float(calc_sma(close, 50).iloc[-1])

            if pd.isna(sma50):
                continue

            total += 1
            if last > sma50:
                above_50 += 1

            if len(close) >= 2:
                if float(close.iloc[-1]) > float(close.iloc[-2]):
                    advancing += 1
                else:
                    declining += 1

            high_50d = float(close.tail(50).max())
            low_50d = float(close.tail(50).min())
            if last >= high_50d * 0.98:
                near_highs += 1
            if last <= low_50d * 1.02:
                near_lows += 1

        except Exception:
            continue

    if total == 0:
        return {"score": 0.5, "pct_above_50sma": 50, "total": 0}

    pct = above_50 / total * 100
    ad_ratio = advancing / max(declining, 1)

    # Score
    score = 0
    if pct >= 55:
        score += 1
    elif pct >= 40:
        score += 0.5

    if ad_ratio >= 1.2:
        score += 0.5
    elif ad_ratio >= 0.8:
        score += 0.25

    if near_highs > near_lows:
        score += 0.5
    elif near_highs == near_lows:
        score += 0.25

    normalized = min(score / 2.0, 1.0)

    return {
        "score": round(normalized, 2),
        "pct_above_50sma": round(pct, 1),
        "above_50sma": above_50,
        "total": total,
        "advancing": advancing,
        "declining": declining,
        "ad_ratio": round(ad_ratio, 2),
        "near_highs": near_highs,
        "near_lows": near_lows,
    }


def calc_sector_rs(sector_data, spy_data, sector_ticker):
    """Forza relativa settore vs SPY."""
    sec_close = get_ticker_close(sector_data, sector_ticker)
    spy_close = get_ticker_close(spy_data, "SPY")

    if sec_close is None or spy_close is None or len(sec_close) < 20 or len(spy_close) < 20:
        return {"score": 0, "rs_diff": 0}

    sec_ret = (float(sec_close.iloc[-1]) / float(sec_close.iloc[-20]) - 1) * 100
    spy_ret = (float(spy_close.iloc[-1]) / float(spy_close.iloc[-20]) - 1) * 100
    rs_diff = sec_ret - spy_ret

    ema21 = calc_ema(sec_close, 21)
    above_ema = float(sec_close.iloc[-1]) > float(ema21.iloc[-1])

    if rs_diff > 0.5 and above_ema:
        score = 1.0
    elif rs_diff > 0:
        score = 0.7
    elif rs_diff > -0.5:
        score = 0.4
    else:
        score = 0

    return {
        "score": round(score, 2),
        "sector_return": round(sec_ret, 2),
        "spy_return": round(spy_ret, 2),
        "rs_diff": round(rs_diff, 2),
        "above_ema21": above_ema,
    }


def build_data():
    """Funzione principale che genera tutti i dati."""
    print("=== Market Context Scorer - Data Builder ===")
    print(f"Data: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    output = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "portfolio_value": PORTFOLIO_VALUE,
    }

    # ── 1. Download dati indici ──
    print("\n[1/4] Scarico dati indici...")
    all_market = list(MARKET_TICKERS.keys())
    market_data = download_safe(all_market, period="1y")

    market_results = {}
    for ticker, name in MARKET_TICKERS.items():
        analysis = analyze_index(market_data, ticker)
        if analysis:
            analysis["name"] = name
            market_results[ticker] = analysis
            print(f"  {ticker} ({name}): ${analysis['price']} | 1d: {analysis['change_1d']:+.2f}% | EMA21: {'above' if analysis['above_ema21'] else 'BELOW'}")

    output["market_indices"] = market_results

    # ── 2. Trend score (A1) ──
    print("\n[2/4] Calcolo trend score...")
    qqq_analysis = market_results.get("QQQ")
    spy_analysis = market_results.get("SPY")

    trend_qqq = calc_trend_score(qqq_analysis)
    trend_spy = calc_trend_score(spy_analysis)
    trend_score = round((trend_qqq + trend_spy) / 2, 2)

    output["a1_trend"] = {
        "score": trend_score,
        "qqq_score": round(trend_qqq, 2),
        "spy_score": round(trend_spy, 2),
        "details": {
            "QQQ": {
                "above_ema21": qqq_analysis["above_ema21"] if qqq_analysis else False,
                "ema_aligned": qqq_analysis["ema_aligned"] if qqq_analysis else False,
                "above_sma200": qqq_analysis["above_sma200"] if qqq_analysis else False,
                "hh_hl": qqq_analysis["hh_hl"] if qqq_analysis else False,
                "ema21_slope": qqq_analysis["ema21_slope"] if qqq_analysis else 0,
            },
            "SPY": {
                "above_ema21": spy_analysis["above_ema21"] if spy_analysis else False,
                "ema_aligned": spy_analysis["ema_aligned"] if spy_analysis else False,
                "above_sma200": spy_analysis["above_sma200"] if spy_analysis else False,
                "hh_hl": spy_analysis["hh_hl"] if spy_analysis else False,
                "ema21_slope": spy_analysis["ema21_slope"] if spy_analysis else 0,
            },
        }
    }
    print(f"  A1 Trend: {trend_score}/1.00 (QQQ: {trend_qqq}, SPY: {trend_spy})")

    # ── 3. Breadth score (A2) ──
    print("\n[3/4] Calcolo breadth (scarico ~80 titoli)...")
    breadth_data = download_safe(BREADTH_UNIVERSE, period="3mo")
    breadth = calc_breadth(breadth_data)
    output["a2_breadth"] = breadth
    print(f"  A2 Breadth: {breadth['score']}/1.00 | {breadth['pct_above_50sma']:.1f}% sopra 50 SMA | A/D: {breadth.get('ad_ratio', 'N/A')}")

    # ── 4. Settori e RS (A3) ──
    print("\n[4/4] Scarico dati settoriali...")
    all_sectors = list(SECTOR_TICKERS.keys())
    sector_data = download_safe(all_sectors, period="6mo")
    spy_only = download_safe("SPY", period="6mo")

    sector_results = {}
    for ticker, name in SECTOR_TICKERS.items():
        analysis = analyze_index(sector_data, ticker)
        rs = calc_sector_rs(sector_data, spy_only, ticker)

        if analysis:
            sector_results[ticker] = {
                "name": name,
                "price": analysis["price"],
                "change_1d": analysis["change_1d"],
                "change_1w": analysis["change_1w"],
                "change_4w": analysis["change_4w"],
                "above_ema21": analysis["above_ema21"],
                "ema_aligned": analysis["ema_aligned"],
                "sparkline": analysis["sparkline"],
                "rs_score": rs["score"],
                "rs_diff": rs["rs_diff"],
                "sector_return_4w": rs.get("sector_return", 0),
            }

    # Rank by RS diff
    ranked = sorted(sector_results.items(), key=lambda x: x[1]["rs_diff"], reverse=True)
    for i, (ticker, data) in enumerate(ranked):
        sector_results[ticker]["rank"] = i + 1

    output["sectors"] = sector_results

    # Default sector (SMH) score
    smh_rs = sector_results.get("SMH", {}).get("rs_score", 0)
    output["a3_sector"] = {
        "default_sector": "SMH",
        "score": smh_rs,
        "all_scores": {t: d["rs_score"] for t, d in sector_results.items()},
    }
    print(f"  A3 Settore (SMH): {smh_rs}/1.00")

    # ── SCORE FINALE ──
    total = trend_score + breadth["score"] + smh_rs
    output["total_score"] = round(total, 2)

    # Semaforo e risk sizing
    if total >= 2.5:
        verdict = "green"
        risk_pct = 0.25
        max_trades = 3
    elif total >= 2.0:
        verdict = "yellow"
        risk_pct = 0.15
        max_trades = 2
    elif total >= 1.5:
        verdict = "orange"
        risk_pct = 0.10
        max_trades = 1
    else:
        verdict = "red"
        risk_pct = 0
        max_trades = 0

    risk_dollar = round(PORTFOLIO_VALUE * risk_pct / 100)
    weekly_budget = round(PORTFOLIO_VALUE * 0.005 * (1 if total >= 2.0 else 0.5))

    output["verdict"] = {
        "signal": verdict,
        "risk_pct": risk_pct,
        "risk_dollar": risk_dollar,
        "max_trades_week": max_trades,
        "weekly_loss_budget": weekly_budget,
    }

    print(f"\n{'='*50}")
    print(f"  SCORE TOTALE: {total:.1f} / 3.0 — SEMAFORO: {verdict.upper()}")
    print(f"  Rischio/trade: ${risk_dollar:,} ({risk_pct}%)")
    print(f"{'='*50}")

    # ── Salva JSON ──
    out_dir = os.environ.get("OUT_DIR", "data")
    os.makedirs(out_dir, exist_ok=True)

    out_path = os.path.join(out_dir, "market_data.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n  Salvato in {out_path}")

    # Salva anche storico giornaliero (append)
    history_path = os.path.join(out_dir, "score_history.json")
    history = []
    if os.path.exists(history_path):
        try:
            with open(history_path) as f:
                history = json.load(f)
        except:
            history = []

    history.append({
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "total": total,
        "a1": trend_score,
        "a2": breadth["score"],
        "a3": smh_rs,
        "signal": verdict,
        "pct_above_50sma": breadth["pct_above_50sma"],
    })

    # Tieni solo ultimi 90 giorni
    history = history[-90:]
    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)

    print(f"  Storico aggiornato ({len(history)} giorni)")
    return output


if __name__ == "__main__":
    build_data()
