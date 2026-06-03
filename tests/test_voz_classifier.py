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


from scrapers.voz import _detect_source, _is_garbage_title, _topic_bonus, _detect_topic, _source_bonus


class TestDetectSource:
    def test_detect_f33(self):
        assert _detect_source("https://voz.vn/f/diem-bao.33/page-2") == "voz_f33"

    def test_detect_cntt(self):
        assert _detect_source("https://voz.vn/f/lap-trinh-cntt.91/") == "voz_cntt"

    def test_detect_ktl(self):
        assert _detect_source("https://voz.vn/f/kinh-te-luat.92/") == "voz_ktl"

    def test_detect_unknown(self):
        assert _detect_source("https://voz.vn/f/random.99/") is None
        assert _detect_source("https://google.com") is None


class TestIsGarbageTitle:
    def test_garbage_detected(self):
        assert _is_garbage_title("Showbiz Việt: Lộ clip nóng") is True
        assert _is_garbage_title("Cướp ngân hàng ở SG") is True
        assert _is_garbage_title("Chuyện vợ chồng và ngoại tình") is True

    def test_clean_title_passes(self):
        assert _is_garbage_title("Fed giữ nguyên lãi suất") is False
        assert _is_garbage_title("Tuyển dụng dev backend") is False


class TestTopicBonus:
    def test_strong_keyword(self):
        assert _topic_bonus("Fed tăng lãi suất") == 1.0

    def test_medium_keyword(self):
        assert _topic_bonus("Startup Việt gọi vốn đầu tư") == 0.5

    def test_strong_and_medium(self):
        assert _topic_bonus("AI và data trong chứng khoán") == 1.5

    def test_no_match(self):
        assert _topic_bonus("Hôm nay trời đẹp") == 0.0


class TestDetectTopic:
    def test_macro_finance(self):
        assert _detect_topic("Fed giữ nguyên lãi suất, vàng tăng") == "macro_finance"

    def test_tech_career(self):
        assert _detect_topic("Tuyển dụng backend dev cho startup AI") == "tech_career"

    def test_energy(self):
        assert _detect_topic("Điện mặt trời và pin lưu trữ") == "energy"

    def test_policy_infra(self):
        assert _detect_topic("Nghị định mới về thuế bất động sản") == "policy_infra"

    def test_general(self):
        assert _detect_topic("Hôm nay ăn gì") == "general"


class TestSourceBonus:
    def test_ktl_max(self):
        assert _source_bonus("voz_ktl") == 1.0

    def test_cntt(self):
        assert _source_bonus("voz_cntt") == 0.9

    def test_f33(self):
        assert _source_bonus("voz_f33") == 0.8

    def test_unknown(self):
        assert _source_bonus("unknown") == 0.0
