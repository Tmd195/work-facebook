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
    ("indicator", "in đi kê tơ"), ("pip", "píp"), ("pips", "píp"), ("lots", "lót"), ("lot", "lót"), ("ounce", "ao"), ("margin", "ma gin"),
    ("leverage", "đòn bẩy"), ("spread", "sờ prét"), ("news", "niu"), ("Fed", "Phét"),
    ("Gold", "vàng"), ("Forex", "pho rếch"), ("XAUUSD", "vàng"), ("XAU", "vàng"), ("DXY", "Đê ích y"),
    ("EURUSD", "ơ rô đô"), ("GBPUSD", "bảng Anh đô"), ("USD", "đô"), ("NFP", "En ép pê"), ("CPI", "Xê pê i"),
    ("CHoCH", "chốc"), ("BOS", "bốt"), ("FVG", "ép vê gờ"), ("EMA", "E em a"), ("SMA", "ét em a"),
    ("MA", "em a"), ("RSI", "a ét i"), ("MACD", "mác đê"), ("ATR", "A tê rờ"), ("VWAP", "vê oáp"),
    ("ADX", "a đê ích"), ("SL", "Ét lờ"), ("TP1", "Tê pê một"), ("TP2", "Tê pê hai"), ("TP3", "Tê pê ba"),
    ("TP", "Tê pê"), ("R:R", "Rờ Rờ"), ("RR", "Rờ Rờ"),
    ("H1", "Hát một"), ("H4", "Hát bốn"), ("D1", "Đê một"), ("W1", "Vê kép một"),
    ("M1", "Em một"), ("M5", "Em năm"), ("M15", "Em mười lăm"), ("M30", "Em ba mươi"),
    ("comment", "com men"), ("like", "lai"), ("share", "se"), ("page", "pết"), ("video", "vi đi ô"),
    ("BUY", "bai"), ("SELL", "xeo"), ("Buy", "bai"), ("Sell", "xeo"), ("AI", "Ây ai"),
]
_PATTERNS = [(re.compile(rf"(?<![\w]){re.escape(a)}(?![\w])", re.I if a.islower() else 0), b) for a, b in TERMS]


def _join_thousands(m: re.Match) -> str:
    return m.group(1) + m.group(2)


DIGIT = "không một hai ba bốn năm sáu bảy tám chín".split()


def _price(m: re.Match) -> str:
    """Giá 4 chữ số trở lên có phần lẻ → đọc từng số như dân trade: 4125,85 → "bốn một hai lăm phẩy 85"."""
    out = []
    for i, ch in enumerate(m.group(1)):
        w = DIGIT[int(ch)]
        if ch == "5" and i and m.group(1)[i - 1] != "0":
            w = "lăm"
        out.append(w)
    return " ".join(out) + " phẩy " + m.group(2)


def _num(n: str) -> str:
    """0–99 thành chữ (aidancing nuốt chữ "phẩy" khi kẹp giữa 2 con số: "0 phẩy 1" bị đọc "0 1")."""
    if len(n) > 1 and n.startswith("0"):
        return " ".join(DIGIT[int(c)] for c in n)          # 0,05 → không phẩy không năm
    v = int(n)
    if v < 10:
        return DIGIT[v]
    tens, one = divmod(v, 10)
    head = "mười" if tens == 1 else DIGIT[tens] + " mươi"
    tail = {0: "", 1: " mốt" if tens > 1 else " một", 4: " tư" if tens > 1 else " bốn", 5: " lăm"}.get(one, " " + DIGIT[one])
    return head + tail


def _small_decimal(m: re.Match) -> str:
    return f"{_num(m.group(1))} phẩy {_num(m.group(2))}"


def spoken(text: str) -> str:
    # Quy tắc đọc anh chốt cho aidancing (13/10/2026): "1 lót", "0 phẩy 1 lót", "Rờ Rờ 1 2",
    # giá "bốn một hai lăm phẩy 85", "2 chấm 7 rờ", "Pết", "píp", "nhá" thay "nhé".
    text = re.sub(r"(\d),(\d{3})(?=\.\d)", _join_thousands, text)      # 4,168.08 → 4168.08
    text = re.sub(r"(\d)\.(\d{3})(?=,\d)", _join_thousands, text)      # 4.168,08 → 4168,08
    text = re.sub(r"(\d)[.,](\d{3})(?![\d.,])", _join_thousands, text)     # 1,000 → 1000
    t = text
    t = re.sub(r"\b(\d{4,})[.,](\d+)", _price, t)                        # giá vàng 4125,85
    t = re.sub(r"\b(R:R|RR)\s*(\d+(?:[.,]\d+)?)\s*:\s*(\d+(?:[.,]\d+)?)", r"\1 \2 \3", t)   # RR 1:2 → RR 1 2
    t = re.sub(r"(\d+)[.,](\d+)\s*R\b", r"\1 chấm \2 rờ", t)              # 2.7R → 2 chấm 7 rờ
    t = re.sub(r"(\d+)\s*R\b", r"\1 rờ", t)                                # 3R → 3 rờ
    t = re.sub(r"\bnhé\b", "nhá", t)
    t = re.sub(r"(\d+)[.,](\d+)\s*%", r"\1 phẩy \2 phần trăm", t)
    t = re.sub(r"(\d+)\s*%", r"\1 phần trăm", t)
    t = re.sub(r"(\d+)\s*:\s*(\d+)", r"\1 ăn \2", t)                    # tỉ lệ 1:2
    t = re.sub(r"(\d+)[.,](\d+)", r"\1 phẩy \2", t)
    t = re.sub(r"(\d+)\s*x\b", r"\1 lần", t)
    t = re.sub(r"\b(\d{1,2}) phẩy (\d{1,2})\b", _small_decimal, t)      # 0,1 → không phẩy một (aidancing nuốt "phẩy" giữa 2 số)
    for pat, rep in _PATTERNS:
        t = pat.sub(rep, t)
    t = t.replace("/", " trên ").replace("&", " và ").replace("+", " cộng ")
    t = re.sub(r"\s*[-–—]\s*", ", ", t)                                 # gạch nối → ngắt hơi
    return re.sub(r"\s{2,}", " ", t).strip()
