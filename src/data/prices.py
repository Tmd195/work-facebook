"""Dữ liệu giá nến D1.

Nguồn:
- Twelve Data (miễn phí 800 lượt/ngày, cần TWELVEDATA_API_KEY) cho XAUUSD/EURUSD/GBPUSD - giá spot chuẩn.
- Yahoo Finance (không cần key) làm dự phòng và cho DXY.
  Yahoo không có vàng spot, nên dùng hợp đồng GC=F rồi điều chỉnh chênh lệch (basis)
  theo giá spot hiện tại từ gold-api.com.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests

from src.config import env

UA = {"User-Agent": "Mozilla/5.0"}
YAHOO_SYMBOL = {"XAUUSD": "GC=F", "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "DXY": "DX-Y.NYB"}
TWELVE_SYMBOL = {"XAUUSD": "XAU/USD", "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD"}


@dataclass
class Candle:
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Series:
    code: str
    candles: list[Candle]
    last: float                  # giá mới nhất
    source: str
    notes: list[str] = field(default_factory=list)


def _twelve(code: str, key: str) -> Series:
    resp = requests.get(
        "https://api.twelvedata.com/time_series",
        params={"symbol": TWELVE_SYMBOL[code], "interval": "1day", "outputsize": 150, "apikey": key},
        timeout=30,
    )
    data = resp.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"Twelve Data {code}: {data.get('message')}")
    candles = [
        Candle(datetime.fromisoformat(v["datetime"]).replace(tzinfo=timezone.utc),
               float(v["open"]), float(v["high"]), float(v["low"]), float(v["close"]))
        for v in reversed(data["values"])
    ]
    return Series(code, candles, candles[-1].close, "Twelve Data")


def _yahoo(code: str, range_: str = "6mo") -> Series:
    resp = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{YAHOO_SYMBOL[code]}",
        params={"interval": "1d", "range": range_}, headers=UA, timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()["chart"]["result"][0]
    q = result["indicators"]["quote"][0]
    candles = []
    for i, ts in enumerate(result["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        candles.append(Candle(datetime.fromtimestamp(ts, timezone.utc), o, h, l, c, (q.get("volume") or [0])[i] or 0))
    last = result["meta"].get("regularMarketPrice") or candles[-1].close
    return Series(code, candles, last, "Yahoo Finance")


def _gold_spot() -> float:
    """Giá vàng spot: gold-api.com → dự phòng Twelve Data. Cả hai lỗi thì raise để nơi gọi dùng giá tương lai."""
    import time
    errors = []
    for attempt in range(2):
        try:
            resp = requests.get("https://api.gold-api.com/price/XAU", timeout=20, headers=UA)
            resp.raise_for_status()
            return float(resp.json()["price"])
        except Exception as exc:
            errors.append(f"gold-api: {type(exc).__name__}")
            time.sleep(3)
    key = env("TWELVEDATA_API_KEY")
    if key:
        try:
            r = requests.get("https://api.twelvedata.com/price", params={"symbol": "XAU/USD", "apikey": key},
                             timeout=20).json()
            if "price" in r:
                return float(r["price"])
            errors.append(f"twelvedata: {r.get('message')}")
        except Exception as exc:
            errors.append(f"twelvedata: {type(exc).__name__}")
    raise RuntimeError("Không lấy được giá vàng spot (" + "; ".join(errors) + ")")


def _basis(futures_last: float) -> tuple[float, str]:
    """Chênh lệch spot - tương lai. Không lấy được spot → 0 (dùng giá tương lai, ghi chú lại)."""
    try:
        return _gold_spot() - futures_last, ""
    except Exception as exc:
        print(f"  ! {exc} → dùng giá hợp đồng tương lai GC=F")
        return 0.0, "giá hợp đồng tương lai GC=F (nguồn spot tạm lỗi)"


def _yahoo_gold_adjusted(range_: str = "6mo") -> Series:
    fut = _yahoo("XAUUSD", range_)
    basis, note = _basis(fut.last)
    spot = fut.last + basis
    candles = [Candle(c.date, c.open + basis, c.high + basis, c.low + basis, c.close + basis, c.volume)
               for c in fut.candles]
    return Series("XAUUSD", candles, spot, "Yahoo GC=F + gold-api spot",
                  [f"Nến quy đổi từ GC=F, chênh lệch {basis:+.2f}"])


def _twelve_h1(code: str, key: str) -> Series:
    resp = requests.get(
        "https://api.twelvedata.com/time_series",
        params={"symbol": TWELVE_SYMBOL[code], "interval": "1h", "outputsize": 300, "apikey": key,
                "timezone": "UTC"},
        timeout=30,
    )
    data = resp.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"Twelve Data {code}: {data.get('message')}")
    candles = [
        Candle(datetime.fromisoformat(v["datetime"]).replace(tzinfo=timezone.utc),
               float(v["open"]), float(v["high"]), float(v["low"]), float(v["close"]))
        for v in reversed(data["values"])
    ]
    return Series(code, candles, candles[-1].close, "Twelve Data")


def _yahoo_h1(code: str) -> Series:
    resp = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{YAHOO_SYMBOL[code]}",
        params={"interval": "60m", "range": "3mo"}, headers=UA, timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()["chart"]["result"][0]
    q = result["indicators"]["quote"][0]
    candles = [
        Candle(datetime.fromtimestamp(ts, timezone.utc), q["open"][i], q["high"][i], q["low"][i], q["close"][i],
               (q.get("volume") or [0])[i] or 0)
        for i, ts in enumerate(result["timestamp"])
        if None not in (q["open"][i], q["high"][i], q["low"][i], q["close"][i])
    ]
    last = result["meta"].get("regularMarketPrice") or candles[-1].close
    return Series(code, candles, last, "Yahoo Finance")


def get_m5(code: str) -> Series:
    """Nến M5 ~5 ngày gần nhất (Yahoo). Vàng được quy đổi về giá spot như các khung khác."""
    resp = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{YAHOO_SYMBOL[code]}",
        params={"interval": "5m", "range": "5d"}, headers=UA, timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()["chart"]["result"][0]
    q = result["indicators"]["quote"][0]
    candles = [
        Candle(datetime.fromtimestamp(ts, timezone.utc), q["open"][i], q["high"][i], q["low"][i], q["close"][i],
               (q.get("volume") or [0])[i] or 0)
        for i, ts in enumerate(result["timestamp"])
        if None not in (q["open"][i], q["high"][i], q["low"][i], q["close"][i])
    ]
    last = result["meta"].get("regularMarketPrice") or candles[-1].close
    if code == "XAUUSD":
        basis, _ = _basis(last)
        candles = [Candle(c.date, c.open + basis, c.high + basis, c.low + basis, c.close + basis, c.volume)
                   for c in candles]
        last += basis
    return Series(code, candles, last, "Yahoo Finance 5m")


def get_intraday(code: str) -> Series:
    """Nến H1 khoảng 1 tháng gần nhất."""
    key = env("TWELVEDATA_API_KEY")
    if key and code in TWELVE_SYMBOL:
        try:
            return _twelve_h1(code, key)
        except Exception as exc:
            print(f"  ! Twelve Data H1 lỗi ({exc}), dùng Yahoo")
    series = _yahoo_h1(code)
    if code == "XAUUSD":
        basis, _ = _basis(series.last)
        spot = series.last + basis
        series = Series(code, [Candle(c.date, c.open + basis, c.high + basis, c.low + basis, c.close + basis, c.volume)
                               for c in series.candles], spot, "Yahoo GC=F + gold-api spot",
                        [f"Nến quy đổi từ GC=F, chênh lệch {basis:+.2f}"])
    return series


def get_series(code: str, range_: str = "6mo") -> Series:
    key = env("TWELVEDATA_API_KEY")
    if key and code in TWELVE_SYMBOL:
        try:
            return _twelve(code, key)
        except Exception as exc:  # rơi về nguồn dự phòng
            print(f"  ! Twelve Data lỗi ({exc}), dùng Yahoo")
    if code == "XAUUSD":
        return _yahoo_gold_adjusted(range_)
    return _yahoo(code, range_)
