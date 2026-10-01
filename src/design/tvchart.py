"""Vẽ biểu đồ giao diện TradingView bằng Lightweight Charts™ (thư viện mã nguồn mở của TradingView, Apache 2.0)
rồi chụp lại bằng trình duyệt không giao diện (Playwright).

Dùng:
    chart = TVChart("XAUUSD", "H4", candles, digits=2)
    chart.line(ema_values, "#2962ff", "EMA 20")
    chart.price_line(4150, "#f23645", "Kháng cự")
    chart.rect(i1, i2, p1, p2, fill, border, "Order Block")
    img = chart.render(1920, 1000)       # PIL.Image
"""
import io
import json
from pathlib import Path

from PIL import Image

from src.config import ASSETS

TEMPLATE = Path(__file__).with_name("tv_template.html")
LIB = ASSETS / "vendor" / "lightweight-charts.standalone.production.js"

# Màu mặc định của TradingView - chọn giao diện sáng/tối trong config.yaml → design.chart_theme
_TV_LIGHT = {
    "bg": "#ffffff", "text": "#131722", "grid": "#f0f3fa", "border": "#e0e3eb",
    "up": "#089981", "down": "#f23645", "blue": "#2962ff", "orange": "#ff9800",
    "purple": "#7e57c2", "gray": "#787b86", "teal": "#00897b", "pink": "#e91e63",
}
_TV_DARK = {**_TV_LIGHT, "bg": "#131722", "text": "#d1d4dc", "grid": "#1e222d", "border": "#2a2e39",
            "gray": "#868993"}
from src.design.palette import CHART_THEME  # noqa: E402

TV = _TV_DARK if CHART_THEME == "dark" else _TV_LIGHT
VN_OFFSET = 7 * 3600   # hiển thị trục thời gian theo giờ Việt Nam


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


class TVChart:
    def __init__(self, symbol: str, tf: str, candles: list, digits: int = 2, right_offset: int = 4):
        """candles: list các object có .date (datetime UTC), .open, .high, .low, .close."""
        self.times = [int(c.date.timestamp()) + VN_OFFSET for c in candles]
        self.spec = {
            "symbol": symbol, "tf": tf, "digits": digits, "theme": TV,
            "candles": [{"time": t, "open": c.open, "high": c.high, "low": c.low, "close": c.close}
                        for t, c in zip(self.times, candles)],
            "lines": [], "priceLines": [], "markers": [], "shapes": [], "panes": [], "legendLines": [],
            "rightOffset": right_offset, "timeVisible": tf.upper() not in ("D1", "W1", "MN"),
            "barSpacing": 8, "paneHeight": 150,
        }

    # ------------------------------------------------------------- công cụ vẽ
    def include(self, *prices: float):
        """Mở rộng khung giá để chắc chắn thấy được các mức này (vùng vào lệnh, SL, TP...)."""
        lo, hi = min(prices), max(prices)
        if self.spec.get("extraRange"):
            lo, hi = min(lo, self.spec["extraRange"][0]), max(hi, self.spec["extraRange"][1])
        self.spec["extraRange"] = [lo, hi]

    def line(self, values: list, color: str, legend: str = "", width: int = 2, style: int = 0, gaps: bool = False):
        """gaps=True: chỗ None để trống (đứt nét) thay vì nối liền - dùng cho SuperTrend 2 màu."""
        data = [{"time": t, "value": v} if v is not None else {"time": t}
                for t, v in zip(self.times, values) if v is not None or gaps]
        self.spec["lines"].append({"data": data, "color": color, "width": width, "style": style})
        if legend:
            self.spec["legendLines"].append({"text": legend, "color": color})

    def colored_line(self, values: list, colors: list, legend: str = "", legend_color: str = TV["blue"]):
        data = [{"time": t, "value": v, "color": c} for t, v, c in zip(self.times, values, colors) if v is not None]
        self.spec["lines"].append({"data": data, "color": legend_color, "width": 2})
        if legend:
            self.spec["legendLines"].append({"text": legend, "color": legend_color})

    def price_line(self, price: float, color: str, title: str = "", style: int = 2, width: int = 1):
        self.spec["priceLines"].append({"price": price, "color": color, "title": title, "style": style, "width": width})

    def marker(self, i: int, text: str, above: bool, color: str, shape: str | None = None):
        self.spec["markers"].append({
            "time": self.times[i], "position": "aboveBar" if above else "belowBar", "color": color,
            "shape": shape or ("arrowDown" if above else "arrowUp"), "text": text})

    def rect(self, i1: int, i2: int | None, p1: float, p2: float, color: str, label: str = "",
             alpha: float = 0.18, label_align: str = "right"):
        self.spec["shapes"].append({"type": "rect", "i1": i1, "i2": i2, "p1": p1, "p2": p2,
                                    "fill": rgba(color, alpha), "border": rgba(color, 0.7),
                                    "label": label, "labelColor": color, "labelAlign": label_align})

    def segment(self, i1: int, p1: float, i2: int, p2: float, color: str, label: str = "",
                width: int = 1, dash: list | None = None, arrow: bool = False, label_align: str = "center"):
        self.spec["shapes"].append({"type": "segment", "i1": i1, "p1": p1, "i2": i2, "p2": p2, "color": color,
                                    "label": label, "width": width, "dash": dash, "arrow": arrow,
                                    "labelAlign": label_align})

    def text(self, i: int, p: float, text: str, color: str = "#ffffff", bg: str | None = None, dy: int = 0, size: int = 12):
        self.spec["shapes"].append({"type": "text", "i": i, "p": p, "text": text, "color": color, "bg": bg,
                                    "dy": dy, "size": size})

    def band(self, a: list, b: list, shift: int, up_color: str, down_color: str):
        pts = [[i + shift, x, y] for i, (x, y) in enumerate(zip(a, b)) if x is not None and y is not None]
        self.spec["shapes"].insert(0, {"type": "band", "points": pts, "upColor": up_color, "downColor": down_color})

    def pane(self, series: list):
        """series: [{"kind": "line"|"histogram", "values": [...], "color": "...", "colors": [...], "levels": [70,30]}]"""
        out = []
        for s in series:
            if s["kind"] == "histogram":
                data = [{"time": t, "value": v, "color": c} for t, v, c in zip(self.times, s["values"], s["colors"])]
            else:
                data = [{"time": t, "value": v} for t, v in zip(self.times, s["values"]) if v is not None]
            out.append({"kind": s["kind"], "data": data, "color": s.get("color"), "levels": s.get("levels", [])})
        self.spec["panes"].append({"series": out})

    # ------------------------------------------------------------- chụp ảnh
    def render(self, width: int = 960, height: int = 520, scale: int = 2) -> Image.Image:
        return self.render_probe(width, height, scale)[0]

    def render_probe(self, width: int = 960, height: int = 520, scale: int = 2,
                     probe: list[tuple[float, float]] | None = None) -> tuple[Image.Image, list]:
        """Chụp ảnh + toạ độ pixel (trên ảnh) của các điểm (chỉ số nến, giá) để vẽ hiệu ứng lên đúng chỗ."""
        from playwright.sync_api import sync_playwright

        spec = {**self.spec, "width": width, "height": height}
        html = (TEMPLATE.read_text(encoding="utf-8")
                .replace("__LIB__", LIB.read_text(encoding="utf-8"))
                .replace("__SPEC__", json.dumps(spec))
                .replace("__W__", str(width)).replace("__H__", str(height)))
        with sync_playwright() as p:
            browser = _launch(p)
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=scale)
            page.set_content(html)
            page.wait_for_function("window.__ready === true", timeout=20000)
            png = page.locator("#wrap").screenshot()
            coords = []
            if probe:
                coords = page.evaluate("""pts => pts.map(([i, p]) => [
                    chart.timeScale().logicalToCoordinate(i), candles.priceToCoordinate(p)])""", probe)
                coords = [(x * scale if x is not None else None, y * scale if y is not None else None)
                          for x, y in coords]
            browser.close()
        return Image.open(io.BytesIO(png)).convert("RGBA"), coords


def _launch(p):
    """Ưu tiên Chromium của Playwright (GitHub Actions); trên máy Windows dùng luôn Chrome/Edge có sẵn."""
    try:
        return p.chromium.launch()
    except Exception:
        for channel in ("chrome", "msedge"):
            try:
                return p.chromium.launch(channel=channel)
            except Exception:
                continue
        raise RuntimeError("Không tìm thấy trình duyệt: chạy `playwright install chromium`")
