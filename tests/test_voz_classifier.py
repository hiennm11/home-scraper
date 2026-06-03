"""Tests for voz classifier — pure functions only."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.voz import _normalize_vi


def test_normalize_vi_strips_diacritics():
    assert _normalize_vi("lãi suất") == "lai suat"
    assert _normalize_vi("điện") == "dien"
    assert _normalize_vi("Đề Xuất") == "de xuat"
    assert _normalize_vi("chứng khoán") == "chung khoan"


def test_normalize_vi_preserves_ascii():
    assert _normalize_vi("fed usd ai") == "fed usd ai"
    assert _normalize_vi("ETF 2024") == "etf 2024"


def test_normalize_vi_empty():
    assert _normalize_vi("") == ""
