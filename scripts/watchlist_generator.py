#!/usr/bin/env python3
"""
Watchlist Generator — Potenziali Big Movers
Analizza ~200 ticker US e identifica i candidati con caratteristiche
simili ai grandi movimenti storici (stile Qullamaggie).

Criteri di scoring:
  - Relative Strength vs SPY (0-25 pt)
  - Volume Pattern (0-15 pt)
  - Prossimità ai massimi (0-20 pt)
  - Volatility Contraction / VCP (0-15 pt)
  - Allineamento Trend (0-15 pt)
  - Bonus settore forte (0-10 pt)

Output: data/watchlist.json (top 20 candidati)
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import sys
from datetime import datetime

# ── UNIVERSO TICKER ──
# ~200 titoli liquidi US raggruppati per settore.
# Comprende mega-cap, growth, mid-cap momentum, IPO recenti.

UNIVERSE = {
    # ── Technology ──
    "AAPL":  ("Apple", "Technology"),
    "MSFT":  ("Microsoft", "Technology"),
    "NVDA":  ("NVIDIA", "Technology"),
    "AVGO":  ("Broadcom", "Technology"),
    "ADBE":  ("Adobe", "Technology"),
    "CRM":   ("Salesforce", "Technology"),
    "AMD":   ("AMD", "Technology"),
    "INTC":  ("Intel", "Technology"),
    "ORCL":  ("Oracle", "Technology"),
    "NOW":   ("ServiceNow", "Technology"),
    "QCOM":  ("Qualcomm", "Technology"),
    "AMAT":  ("Applied Materials", "Technology"),
    "MU":    ("Micron", "Technology"),
    "LRCX":  ("Lam Research", "Technology"),
    "KLAC":  ("KLA Corp", "Technology"),
    "SNPS":  ("Synopsys", "Technology"),
    "CDNS":  ("Cadence", "Technology"),
    "MRVL":  ("Marvell", "Technology"),
    "ARM":   ("ARM Holdings", "Technology"),
    "PANW":  ("Palo Alto Networks", "Technology"),
    "CRWD":  ("CrowdStrike", "Technology"),
    "SNOW":  ("Snowflake", "Technology"),
    "DDOG":  ("Datadog", "Technology"),
    "ZS":    ("Zscaler", "Technology"),
    "NET":   ("Cloudflare", "Technology"),
    "TEAM":  ("Atlassian", "Technology"),
    "WDAY":  ("Workday", "Technology"),
    "HUBS":  ("HubSpot", "Technology"),
    "SHOP":  ("Shopify", "Technology"),
    "MNDY":  ("monday.com", "Technology"),
    "SMCI":  ("Super Micro", "Technology"),
    "DELL":  ("Dell Technologies", "Technology"),
    "HPE":   ("Hewlett Packard Ent.", "Technology"),
    "GDDY":  ("GoDaddy", "Technology"),
    "VEEV":  ("Veeva Systems", "Technology"),
    "FTNT":  ("Fortinet", "Technology"),
    "ABNB":  ("Airbnb", "Technology"),

    # ── Semiconductors ──
    "TSM":   ("TSMC", "Semiconductors"),
    "ASML":  ("ASML", "Semiconductors"),
    "TXN":   ("Texas Instruments", "Semiconductors"),
    "ON":    ("ON Semiconductor", "Semiconductors"),
    "MCHP":  ("Microchip Tech", "Semiconductors"),
    "ADI":   ("Analog Devices", "Semiconductors"),
    "SWKS":  ("Skyworks", "Semiconductors"),

    # ── Consumer / Internet ──
    "AMZN":  ("Amazon", "Consumer"),
    "TSLA":  ("Tesla", "Consumer"),
    "GOOG":  ("Alphabet", "Consumer"),
    "META":  ("Meta Platforms", "Consumer"),
    "NFLX":  ("Netflix", "Consumer"),
    "UBER":  ("Uber", "Consumer"),
    "DASH":  ("DoorDash", "Consumer"),
    "SPOT":  ("Spotify", "Consumer"),
    "PINS":  ("Pinterest", "Consumer"),
    "TTD":   ("The Trade Desk", "Consumer"),
    "ROKU":  ("Roku", "Consumer"),
    "RBLX":  ("Roblox", "Consumer"),
    "DUOL":  ("Duolingo", "Consumer"),
    "APP":   ("AppLovin", "Consumer"),
    "RDDT":  ("Reddit", "Consumer"),
    "SNAP":  ("Snap", "Consumer"),
    "COIN":  ("Coinbase", "Consumer"),
    "HOOD":  ("Robinhood", "Consumer"),
    "SQ":    ("Block (Square)", "Consumer"),
    "TOST":  ("Toast", "Consumer"),
    "CART":  ("Instacart", "Consumer"),

    # ── Consumer Discretionary / Retail ──
    "HD":    ("Home Depot", "Retail"),
    "LOW":   ("Lowe's", "Retail"),
    "NKE":   ("Nike", "Retail"),
    "SBUX":  ("Starbucks", "Retail"),
    "MCD":   ("McDonald's", "Retail"),
    "TJX":   ("TJX Companies", "Retail"),
    "BKNG":  ("Booking Holdings", "Retail"),
    "CMG":   ("Chipotle", "Retail"),
    "LULU":  ("Lululemon", "Retail"),
    "DECK":  ("Deckers Outdoor", "Retail"),
    "ELF":   ("e.l.f. Beauty", "Retail"),
    "CELH":  ("Celsius Holdings", "Retail"),
    "MNST":  ("Monster Beverage", "Retail"),
    "ONON":  ("On Holding", "Retail"),
    "BIRK":  ("Birkenstock", "Retail"),
    "CAVA":  ("CAVA Group", "Retail"),
    "DPZ":   ("Domino's Pizza", "Retail"),
    "COST":  ("Costco", "Retail"),
    "WMT":   ("Walmart", "Retail"),
    "TGT":   ("Target", "Retail"),

    # ── Healthcare / Biotech ──
    "UNH":   ("UnitedHealth", "Healthcare"),
    "LLY":   ("Eli Lilly", "Healthcare"),
    "JNJ":   ("J&J", "Healthcare"),
    "PFE":   ("Pfizer", "Healthcare"),
    "ABBV":  ("AbbVie", "Healthcare"),
    "MRK":   ("Merck", "Healthcare"),
    "TMO":   ("Thermo Fisher", "Healthcare"),
    "ABT":   ("Abbott Labs", "Healthcare"),
    "ISRG":  ("Intuitive Surgical", "Healthcare"),
    "DXCM":  ("DexCom", "Healthcare"),
    "PODD":  ("Insulet", "Healthcare"),
    "INSP":  ("Inspire Medical", "Healthcare"),
    "AXON":  ("Axon Enterprise", "Healthcare"),
    "AMGN":  ("Amgen", "Healthcare"),
    "GILD":  ("Gilead Sciences", "Healthcare"),
    "VRTX":  ("Vertex Pharma", "Healthcare"),
    "REGN":  ("Regeneron", "Healthcare"),
    "DHR":   ("Danaher", "Healthcare"),

    # ── Financials ──
    "JPM":   ("JPMorgan Chase", "Financials"),
    "V":     ("Visa", "Financials"),
    "MA":    ("Mastercard", "Financials"),
    "BAC":   ("Bank of America", "Financials"),
    "WFC":   ("Wells Fargo", "Financials"),
    "GS":    ("Goldman Sachs", "Financials"),
    "MS":    ("Morgan Stanley", "Financials"),
    "BLK":   ("BlackRock", "Financials"),
    "SCHW":  ("Charles Schwab", "Financials"),
    "AXP":   ("American Express", "Financials"),
    "ICE":   ("Intercont. Exchange", "Financials"),
    "CME":   ("CME Group", "Financials"),

    # ── Industrials ──
    "CAT":   ("Caterpillar", "Industrials"),
    "UNP":   ("Union Pacific", "Industrials"),
    "HON":   ("Honeywell", "Industrials"),
    "BA":    ("Boeing", "Industrials"),
    "RTX":   ("RTX Corp", "Industrials"),
    "DE":    ("Deere & Co", "Industrials"),
    "LMT":   ("Lockheed Martin", "Industrials"),
    "GE":    ("GE Aerospace", "Industrials"),
    "FDX":   ("FedEx", "Industrials"),
    "GEV":   ("GE Vernova", "Industrials"),
    "UBER":  ("Uber", "Industrials"),
    "PWR":   ("Quanta Services", "Industrials"),
    "EME":   ("EMCOR Group", "Industrials"),

    # ── Energy ──
    "XOM":   ("Exxon Mobil", "Energy"),
    "CVX":   ("Chevron", "Energy"),
    "COP":   ("ConocoPhillips", "Energy"),
    "SLB":   ("Schlumberger", "Energy"),
    "EOG":   ("EOG Resources", "Energy"),
    "MPC":   ("Marathon Petroleum", "Energy"),
    "OXY":   ("Occidental", "Energy"),
    "VLO":   ("Valero Energy", "Energy"),
    "PSX":   ("Phillips 66", "Energy"),
    "HES":   ("Hess Corp", "Energy"),

    # ── Communication ──
    "DIS":   ("Walt Disney", "Communication"),
    "CMCSA": ("Comcast", "Communication"),
    "T":     ("AT&T", "Communication"),
    "VZ":    ("Verizon", "Communication"),
    "TMUS":  ("T-Mobile", "Communication"),
    "EA":    ("Electronic Arts", "Communication"),
    "TTWO":  ("Take-Two", "Communication"),
    "WBD":   ("Warner Bros", "Communication"),

    # ── New Energy / Infra ──
    "ENPH":  ("Enphase Energy", "New Energy"),
    "FSLR":  ("First Solar", "New Energy"),
    "VST":   ("Vistra Corp", "New Energy"),
    "CEG":   ("Constellation Energy", "New Energy"),
    "TLN":   ("Talen Energy", "New Energy"),
    "SMR":   ("NuScale Power", "New Energy"),
    "OKLO":  ("Oklo", "New Energy"),

    # ── Aerospace / Defense / Space ──
    "RKLB":  ("Rocket Lab", "Aerospace"),
    "ASTS":  ("AST SpaceMobile", "Aerospace"),
    "LUNR":  ("Intuitive Machines", "Aerospace"),
    "PLTR":  ("Palantir", "Aerospace"),
    "AXON":  ("Axon Enterprise", "Aerospace"),

    # ── Crypto / Fintech ──
    "MSTR":  ("MicroStrategy", "Crypto"),
    "MARA":  ("Marathon Digital", "Crypto"),
    "RIOT":  ("Riot Platforms", "Crypto"),
    "CLSK":  ("CleanSpark", "Crypto"),

    # ── AI / Quantum ──
    "IONQ":  ("IonQ", "AI/Quantum"),
    "RGTI":  ("Rigetti Computing", "AI/Quantum"),
    "AI":    ("C3.ai", "AI/Quantum"),
    "BBAI":  ("BigBear.ai", "AI/Quantum"),
    "SOUN":  ("SoundHound AI", "AI/Quantum"),
    "UPST":  ("Upstart", "AI/Quantum"),

    # ── Metals & Mining ──
    "NEM":   ("Newmont", "Metals"),
    "FCX":   ("Freeport-McMoRan", "Metals"),
    "CLF":   ("Cleveland-Cliffs", "Metals"),
    "AA":    ("Alcoa", "Metals"),
}

# Rimuovi duplicati (UBER e AXON appaiono 2 volte)
# Usa la prima occorrenza
_seen = set()
UNIVERSE_CLEAN = {}
for ticker, (name, sector) in UNIVERSE.items():
    if ticker not in _seen:
        UNIVERSE_CLEAN[ticker] = (name, sector)
        _seen.add(ticker)
UNIVERSE = UNIVERSE_CLEAN

# Mappa settore → ETF settoriale (per bonus RS dal market_data.json)
SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Semiconductors": "SMH",
    "Consumer": "XLY",
    "Retail": "XLY",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Communication": "XLC",
    "New Energy": "TAN",
    "Aerospace": "XLI",
    "Crypto": "BITQ",
    "AI/Quantum": "XLK",
    "Metals": "XME",
}

# ── CONFIGURAZIONE SCORING ──
TOP_N = 20  # Numero candidati in output


def download_safe(tickers, period="6mo", interval="1d"):
    """Download con gestione errori."""
    try:
        if isinstance(tickers, list):
            tickers = " ".join(tickers)
        df = yf.download(
            tickers, period=period, interval=interval,
            progress=False, auto_adjust=True, threads=True,
        )
        return df
    except Exception as e:
        print(f"  ERRORE download: {e}", file=sys.stderr)
        return None


def get_close(data, ticker):
    """Estrai close per un ticker da dati multi o singoli."""
    if data is None:
        return None
    if isinstance(data.columns, pd.MultiIndex):
        if ticker in data.columns.get_level_values(1):
            return data["Close"][ticker].dropna()
        return None
    return data["Close"].dropna()


def get_volume(data, ticker):
    """Estrai volume per un ticker."""
    if data is None:
        return None
    if isinstance(data.columns, pd.MultiIndex):
        if ticker in data.columns.get_level_values(1):
            return data["Volume"][ticker].dropna()
        return None
    return data["Volume"].dropna()


def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def calc_sma(series, period):
    return series.rolling(window=period).mean()


def calc_atr(high, low, close, period=14):
    """Average True Range."""
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def score_rs(stock_close, spy_close, periods=(20,)):
    """
    Relative Strength vs SPY (0-25 punti).
    Usa il rendimento a 4 settimane relativo a SPY.
    """
    if stock_close is None or spy_close is None:
        return 0, 0.0

    if len(stock_close) < 20 or len(spy_close) < 20:
        return 0, 0.0

    stock_ret = (float(stock_close.iloc[-1]) / float(stock_close.iloc[-20]) - 1) * 100
    spy_ret = (float(spy_close.iloc[-1]) / float(spy_close.iloc[-20]) - 1) * 100
    rs_diff = stock_ret - spy_ret

    if rs_diff >= 10:
        pts = 25
    elif rs_diff >= 5:
        pts = 20
    elif rs_diff >= 2:
        pts = 15
    elif rs_diff >= 0:
        pts = 8
    elif rs_diff >= -2:
        pts = 3
    else:
        pts = 0

    return pts, round(rs_diff, 2)


def score_volume(volume):
    """
    Volume Pattern (0-15 punti).
    Rapporto tra volume medio recente (5gg) e volume medio 50gg.
    """
    if volume is None or len(volume) < 50:
        return 0, 0.0

    avg_5 = float(volume.tail(5).mean())
    avg_50 = float(volume.tail(50).mean())

    if avg_50 == 0:
        return 0, 0.0

    ratio = avg_5 / avg_50

    if ratio >= 2.0:
        pts = 15
    elif ratio >= 1.5:
        pts = 12
    elif ratio >= 1.2:
        pts = 8
    elif ratio >= 1.0:
        pts = 4
    else:
        pts = 0

    return pts, round(ratio, 2)


def score_proximity_high(close):
    """
    Prossimità al massimo 52w (0-20 punti).
    Più è vicino, meglio è — indica forza.
    """
    if close is None or len(close) < 50:
        return 0, 0.0

    last = float(close.iloc[-1])
    high_all = float(close.max())  # max nel periodo scaricato (~6 mesi)

    if high_all == 0:
        return 0, 0.0

    dist_pct = (last / high_all - 1) * 100  # negativo = sotto il max

    if dist_pct >= -2:
        pts = 20
    elif dist_pct >= -5:
        pts = 16
    elif dist_pct >= -10:
        pts = 10
    elif dist_pct >= -15:
        pts = 5
    else:
        pts = 0

    return pts, round(dist_pct, 2)


def score_vcp(close):
    """
    Volatility Contraction Pattern (0-15 punti).
    Confronta ATR recente (10gg) vs ATR a 50gg.
    Un rapporto basso indica contrazione della volatilità.
    """
    if close is None or len(close) < 50:
        return 0, "N/A"

    # Calcolo ATR semplificato usando range giornaliero
    daily_range = close.pct_change().abs()
    atr_10 = float(daily_range.tail(10).mean())
    atr_50 = float(daily_range.tail(50).mean())

    if atr_50 == 0:
        return 0, "N/A"

    contraction = atr_10 / atr_50

    if contraction <= 0.6:
        pts = 15
        label = "TIGHT"
    elif contraction <= 0.8:
        pts = 10
        label = "MODERATE"
    elif contraction <= 1.0:
        pts = 5
        label = "NORMAL"
    else:
        pts = 0
        label = "EXPANDING"

    return pts, label


def score_trend(close):
    """
    Allineamento Trend (0-15 punti).
    Prezzo > EMA21 > EMA50 = trend perfetto.
    """
    if close is None or len(close) < 50:
        return 0, "N/A"

    last = float(close.iloc[-1])
    ema21 = float(calc_ema(close, 21).iloc[-1])
    ema50 = float(calc_ema(close, 50).iloc[-1])

    above_ema21 = last > ema21
    ema_aligned = ema21 > ema50

    # Slope EMA21 (5 giorni)
    ema21_series = calc_ema(close, 21)
    if len(ema21_series) >= 5:
        ema_5ago = float(ema21_series.iloc[-5])
        slope_up = ema21 > ema_5ago
    else:
        slope_up = False

    if above_ema21 and ema_aligned and slope_up:
        pts = 15
        label = "STRONG"
    elif above_ema21 and ema_aligned:
        pts = 12
        label = "ALIGNED"
    elif above_ema21:
        pts = 7
        label = "ABOVE"
    else:
        pts = 0
        label = "BELOW"

    return pts, label


def score_sector_bonus(sector, sector_rs_data):
    """
    Bonus settore forte (0-10 punti).
    Cross-reference con dati settoriali da market_data.json.
    """
    etf = SECTOR_ETF_MAP.get(sector)
    if not etf or not sector_rs_data:
        return 0

    sector_info = sector_rs_data.get(etf, {})
    rs_diff = sector_info.get("rs_diff", 0)
    rs_score = sector_info.get("rs_score", 0)

    if rs_diff > 2 and rs_score >= 0.7:
        return 10
    elif rs_diff > 0.5:
        return 7
    elif rs_diff > 0:
        return 4
    else:
        return 0


def build_signals(rs_pts, vol_pts, prox_pts, vcp_pts, trend_pts, sector_pts):
    """Genera lista di segnali attivi."""
    signals = []
    if rs_pts >= 15:
        signals.append("RS_STRONG")
    if vol_pts >= 8:
        signals.append("VOL_SURGE")
    if prox_pts >= 16:
        signals.append("NEAR_HIGH")
    if vcp_pts >= 10:
        signals.append("VCP")
    if trend_pts >= 12:
        signals.append("TREND_UP")
    if sector_pts >= 7:
        signals.append("SECTOR_HOT")
    return signals


def generate_watchlist():
    """Funzione principale."""
    print("=== Watchlist Generator — Potenziali Big Movers ===")
    print(f"Data: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    # ── 1. Carica dati settoriali esistenti ──
    out_dir = os.environ.get("OUT_DIR", "data")
    market_data_path = os.path.join(out_dir, "market_data.json")
    sector_rs_data = {}
    market_signal = "unknown"

    if os.path.exists(market_data_path):
        try:
            with open(market_data_path) as f:
                mkt = json.load(f)
            sector_rs_data = mkt.get("sectors", {})
            market_signal = mkt.get("verdict", {}).get("signal", "unknown")
            print(f"  Market signal corrente: {market_signal.upper()}")
        except Exception as e:
            print(f"  Attenzione: impossibile leggere market_data.json: {e}")

    # ── 2. Download dati universo ──
    tickers = list(UNIVERSE.keys())
    print(f"\n[1/3] Scarico dati per {len(tickers)} ticker...")

    all_data = download_safe(tickers, period="6mo")
    if all_data is None or all_data.empty:
        print("ERRORE: Nessun dato scaricato. Uscita.", file=sys.stderr)
        sys.exit(1)

    # SPY come benchmark
    spy_close = get_close(all_data, "SPY")
    if spy_close is None:
        # Download SPY separatamente se non nell'universo
        spy_data = download_safe("SPY", period="6mo")
        spy_close = get_close(spy_data, "SPY")

    # ── 3. Scoring ──
    print(f"\n[2/3] Scoring candidati...")
    candidates = []

    for ticker, (name, sector) in UNIVERSE.items():
        close = get_close(all_data, ticker)
        volume = get_volume(all_data, ticker)

        if close is None or len(close) < 50:
            continue

        last = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) >= 2 else last

        # Calcola tutti gli score
        rs_pts, rs_diff = score_rs(close, spy_close)
        vol_pts, vol_ratio = score_volume(volume)
        prox_pts, dist_high = score_proximity_high(close)
        vcp_pts, vcp_label = score_vcp(close)
        trend_pts, trend_label = score_trend(close)
        sector_pts = score_sector_bonus(sector, sector_rs_data)

        total = rs_pts + vol_pts + prox_pts + vcp_pts + trend_pts + sector_pts
        signals = build_signals(rs_pts, vol_pts, prox_pts, vcp_pts, trend_pts, sector_pts)

        # Performance
        ret_1d = (last / prev - 1) * 100 if prev > 0 else 0
        ret_1w = (last / float(close.iloc[-5]) - 1) * 100 if len(close) >= 5 else 0
        ret_4w = (last / float(close.iloc[-20]) - 1) * 100 if len(close) >= 20 else 0

        # Sparkline (ultimi 30 giorni)
        spark = [float(x) for x in close.tail(30).values]

        candidates.append({
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "score": total,
            "price": round(last, 2),
            "change_1d": round(ret_1d, 2),
            "change_1w": round(ret_1w, 2),
            "change_4w": round(ret_4w, 2),
            "rs_vs_spy": rs_diff,
            "vol_ratio": vol_ratio,
            "dist_from_high": dist_high,
            "vcp": vcp_label,
            "trend": trend_label,
            "signals": signals,
            "sparkline": spark,
            "breakdown": {
                "rs": rs_pts,
                "volume": vol_pts,
                "proximity": prox_pts,
                "vcp": vcp_pts,
                "trend": trend_pts,
                "sector": sector_pts,
            },
        })

    # ── 4. Rank e filtra ──
    candidates.sort(key=lambda x: x["score"], reverse=True)
    top = candidates[:TOP_N]

    print(f"\n[3/3] Top {TOP_N} candidati:")
    print(f"  {'#':<3} {'Ticker':<7} {'Score':<6} {'RS%':<7} {'Vol':<5} {'Trend':<8} {'Segnali'}")
    print(f"  {'─'*60}")
    for i, c in enumerate(top):
        sigs = ", ".join(c["signals"]) if c["signals"] else "—"
        print(f"  {i+1:<3} {c['ticker']:<7} {c['score']:<6} {c['rs_vs_spy']:>+5.1f}% {c['vol_ratio']:>4.1f}x {c['trend']:<8} {sigs}")

    # ── 5. Salva output ──
    output = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "market_signal": market_signal,
        "universe_size": len(tickers),
        "analyzed": len(candidates),
        "candidates": top,
    }

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "watchlist.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n  Salvato in {out_path}")
    return output


if __name__ == "__main__":
    generate_watchlist()
