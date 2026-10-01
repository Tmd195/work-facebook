"""Các mẫu thiết kế Bản tin sáng. Chọn mẫu trong config.yaml -> design.style."""
from src.design import morning_banner as dark
from src.design.styles import block, clean, editorial

STYLES = {
    "editorial": editorial.render,
    "clean": clean.render,
    "block": block.render,
    "dark": dark.render,
}
