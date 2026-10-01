"""Hashtag cho mọi bài: luôn có #DuyThaiDang + hashtag phù hợp nội dung từng bài."""
import re
import unicodedata

BRAND = "#DuyThaiDang"

# Hashtag riêng theo series kiến thức
SERIES_TAGS = {
    "price-action-nhap-mon": ["#PriceAction", "#nentang"], "ho-tro-khang-cu-cung-cau": ["#HoTroKhangCu", "#SupplyDemand"],
    "pivot-point": ["#PivotPoint"], "fibonacci": ["#Fibonacci"], "ma-ema": ["#EMA", "#MovingAverage"],
    "rsi-macd-phan-ky": ["#RSI", "#MACD", "#Divergence"], "quan-ly-von": ["#QuanLyVon", "#RiskManagement"],
    "tam-ly-giao-dich": ["#TamLyGiaoDich", "#TradingPsychology"], "dow-cau-truc-thi-truong": ["#DowTheory", "#MarketStructure"],
    "giao-dich-theo-phien": ["#TradingSession", "#LondonBreakout"], "co-ban-cho-trader-vang": ["#PhanTichCoBan", "#Fed"],
    "trend-following-turtle": ["#TrendFollowing", "#Turtle"], "smc-nhap-mon": ["#SMC", "#SmartMoney"],
    "snr-quasimodo": ["#SNR", "#Quasimodo"], "crt-candle-range-theory": ["#CRT", "#CandleRangeTheory"],
    "ict-chuyen-sau": ["#ICT", "#SmartMoney"], "al-brooks-price-action": ["#AlBrooks", "#PriceAction"],
    "wyckoff": ["#Wyckoff"], "vsa": ["#VSA", "#Volume"], "volume-profile": ["#VolumeProfile"],
    "elliott": ["#ElliottWave"], "harmonic": ["#Harmonic"], "ichimoku": ["#Ichimoku"],
    "supertrend-atr": ["#Supertrend", "#ATR"], "bollinger-keltner-squeeze": ["#BollingerBands", "#Squeeze"],
    "vwap": ["#VWAP"], "bill-williams": ["#BillWilliams", "#Alligator"], "heikin-ashi-tdi": ["#HeikinAshi", "#TDI"],
    "tuong-quan-lien-thi-truong": ["#Correlation", "#DXY"], "canh-bao-he-thong-nguy-hiem": ["#Martingale", "#CanhBao"],
}

CURRENCY_TAGS = {"USD": "#USD", "EUR": "#EURUSD", "GBP": "#GBPUSD"}


def _dedupe(tags: list[str]) -> list[str]:
    seen, out = set(), []
    for t in tags:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    return out


def knowledge(series_id: str) -> str:
    return " ".join(_dedupe([BRAND] + SERIES_TAGS.get(series_id, []) + ["#kienthucforex", "#trading", "#forex"]))


def morning(events: list[dict]) -> str:
    cur = [CURRENCY_TAGS[e["currency"]] for e in events if e.get("impact") == "High" and e["currency"] in CURRENCY_TAGS]
    titles = " ".join(e["title"] for e in events if e.get("impact") == "High").upper()
    topic = [t for k, t in (("CPI", "#CPI"), ("PCE", "#PCE"), ("NON-FARM", "#NFP"), ("FOMC", "#FOMC"),
                            ("GDP", "#GDP"), ("PMI", "#PMI"), ("RATE", "#LaiSuat")) if k in titles]
    return " ".join(_dedupe([BRAND, "#bantinsang", "#XAUUSD", "#giavang"] + cur + topic + ["#forex"]))


def strategy(session: str, bias: str) -> str:
    sess = "#PhienAu" if session == "ae" else "#PhienMy"
    b = {"giảm": "#XuHuongGiam", "tăng": "#XuHuongTang"}.get(bias, "")
    return " ".join(_dedupe([BRAND, "#XAUUSD", "#giavang", "#chienluocvang", sess] + ([b] if b else []) + ["#forex"]))
