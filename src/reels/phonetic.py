"""Chuyển thuật ngữ tiếng Anh / ký hiệu sang cách đọc tiếng Việt cho AI giọng nói (khớp khẩu hình tiếng Việt).

Chỉ áp dụng cho LỜI ĐỌC; chữ hiện trên màn hình vẫn giữ SL, TP, ATR...
Thêm từ mới: bổ sung vào TERMS (từ dài đặt trước từ ngắn cùng gốc).
"""
import re

TERMS = [
    # cụm dài trước
    ("Decode Global & Partner", "Đi cốt Glô bồ và Pát nơ"), ("DecodeFX", "Đi cốt ép ích"), ("Decode", "Đi cốt"),
    ("IB", "ai bi"),
    ("CWG Markets & Partner", "Xi đắp liu gi Mác kịt và Pát nơ"), ("CWG Markets", "Xi đắp liu gi Mác kịt"),
    ("CWG", "Xi đắp liu gi"), ("liquidity sweep", "li quí đi ti xuýp"), ("liquidity", "li quí đi ti"),
    ("accumulation", "ắc kiu mu lây sần"), ("manipulation", "ma ni pu lây sần"), ("distribution", "đít tri biu sần"),
    ("inducement", "in điu xơ mần"), ("smart money", "sờ mát mơ ni"), ("fair value gap", "phe va liu gáp"),
    ("market structure", "cấu trúc thị trường"), ("retest", "ri tét"), ("range", "ren"), ("sweep", "xuýp"),
    ("Power of Three", "pao ơ ọp thờ ri"), ("PO3", "pê ô ba"), ("ICT", "ai xi ti"), ("MSS", "em ét ét"),
    ("OB", "âu bi"), ("SMC", "ét em xi"),
    ("stop loss", "Ét lờ"), ("stoploss", "Ét lờ"), ("take profit", "Tê pê"),
    ("break even", "hoà vốn"), ("breakeven", "hoà vốn"), ("risk reward", "rủi ro trên lợi nhuận"),
    ("price action", "prai ác sần"), ("order block", "o đơ bờ lốc"), ("smart money", "sờ mát mơ ni"),
    ("trailing stop", "trây linh ét lờ"), ("buy limit", "bai li mít"), ("sell limit", "xeo li mít"),
    ("buy stop", "bai sờ tóp"), ("sell stop", "xeo sờ tóp"), ("supertrend", "su pơ tren"),
    ("bollinger", "bô lin giơ"), ("fibonacci", "phi bô na chi"), ("ichimoku", "i chi mô cu"),
    ("backtest", "bách tét"), ("setup", "sét ắp"), ("trading", "trây đinh"), ("trader", "trây đơ"),
    ("trade", "trết"), ("scalping", "sờ cao pinh"), ("scalp", "sờ cao"), ("swing", "xuynh"),
    ("entry", "en try"), ("pullback", "pun béc"), ("breakout", "brếch ao"), ("fakeout", "phếch ao"),
    ("trend", "tren"), ("sideway", "sai uây"), ("volume", "vô lum"), ("signal", "xích nồ"),
    ("indicator", "in đi kê tơ"), ("pip", "píp"), ("pips", "píp"), ("lot", "lốt"), ("margin", "ma gin"),
    ("leverage", "đòn bẩy"), ("spread", "sờ prét"), ("news", "niu"), ("Fed", "Phét"),
    ("Gold", "vàng"), ("Forex", "pho rếch"), ("XAUUSD", "vàng"), ("XAU", "vàng"), ("DXY", "Đê ích y"),
    ("EURUSD", "ơ rô đô"), ("GBPUSD", "bảng Anh đô"), ("USD", "đô"), ("NFP", "En ép pê"), ("CPI", "Xê pê i"),
    ("CHoCH", "chốc"), ("BOS", "bốt"), ("FVG", "ép vê gờ"), ("EMA", "E em a"), ("SMA", "ét em a"),
    ("MA", "em a"), ("RSI", "a ét i"), ("MACD", "mác đê"), ("ATR", "A tê rờ"), ("VWAP", "vê oáp"),
    ("ADX", "a đê ích"), ("SL", "Ét lờ"), ("TP1", "Tê pê một"), ("TP2", "Tê pê hai"), ("TP3", "Tê pê ba"),
    ("TP", "Tê pê"), ("R:R", "tỉ lệ rủi ro trên lợi nhuận"), ("RR", "tỉ lệ rủi ro trên lợi nhuận"),
    ("H1", "Hát một"), ("H4", "Hát bốn"), ("D1", "Đê một"), ("W1", "Vê kép một"),
    ("M1", "Em một"), ("M5", "Em năm"), ("M15", "Em mười lăm"), ("M30", "Em ba mươi"),
    ("comment", "com men"), ("like", "lai"), ("share", "se"), ("page", "pết"), ("video", "vi đi ô"),
    ("BUY", "bai"), ("SELL", "xeo"), ("Buy", "bai"), ("Sell", "xeo"), ("AI", "Ây ai"),
]
_PATTERNS = [(re.compile(rf"(?<![\w]){re.escape(a)}(?![\w])", re.I if a.islower() else 0), b) for a, b in TERMS]


def _join_thousands(m: re.Match) -> str:
    return m.group(1) + m.group(2)


def spoken(text: str) -> str:
    text = re.sub(r"(\d),(\d{3})(?!\d)", _join_thousands, text)   # 4,168.08 → 4168.08
    t = text
    t = re.sub(r"(\d+)[.,](\d+)\s*%", r"\1 phẩy \2 phần trăm", t)
    t = re.sub(r"(\d+)\s*%", r"\1 phần trăm", t)
    t = re.sub(r"(\d+)\s*:\s*(\d+)", r"\1 ăn \2", t)                    # tỉ lệ 1:2
    t = re.sub(r"(\d+)[.,](\d+)", r"\1 phẩy \2", t)
    t = re.sub(r"(\d+)\s*x\b", r"\1 lần", t)
    for pat, rep in _PATTERNS:
        t = pat.sub(rep, t)
    t = t.replace("/", " trên ").replace("&", " và ").replace("+", " cộng ")
    t = re.sub(r"\s*[-–—]\s*", ", ", t)                                 # gạch nối → ngắt hơi
    return re.sub(r"\s{2,}", " ", t).strip()
