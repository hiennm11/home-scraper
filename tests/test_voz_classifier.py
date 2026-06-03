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


from scrapers.voz import _calc_score, _select_threads


class TestCalcScore:
    def test_score_is_positive(self):
        thread = {
            "title": "Fed tăng lãi suất",
            "replies": 150,
            "views": 5000,
            "page_jump": 3,
            "last_activity_at": "2026-06-03T14:00:00+07:00",
        }
        score = _calc_score(thread, "voz_ktl")
        assert score > 0

    def test_higher_replies_higher_score(self):
        t1 = {"title": "A", "replies": 10, "views": 1000, "page_jump": 1,
              "last_activity_at": "2026-06-03T14:00:00+07:00"}
        t2 = {"title": "A", "replies": 100, "views": 1000, "page_jump": 1,
              "last_activity_at": "2026-06-03T14:00:00+07:00"}
        assert _calc_score(t2, "voz_f33") > _calc_score(t1, "voz_f33")

    def test_ktl_beats_f33_all_else_equal(self):
        thread = {"title": "A", "replies": 50, "views": 2000, "page_jump": 2,
                  "last_activity_at": "2026-06-03T14:00:00+07:00"}
        assert _calc_score(thread, "voz_ktl") > _calc_score(thread, "voz_f33")

    def test_old_thread_lower_freshness(self):
        t_new = {"title": "A", "replies": 50, "views": 2000, "page_jump": 2,
                 "last_activity_at": "2026-06-03T14:00:00+07:00"}
        t_old = {"title": "A", "replies": 50, "views": 2000, "page_jump": 2,
                 "last_activity_at": "2026-05-29T14:00:00+07:00"}  # 5 days ago
        assert _calc_score(t_new, "voz_f33") > _calc_score(t_old, "voz_f33")

    def test_missing_last_activity_defaults_to_zero_freshness(self):
        thread = {"title": "A", "replies": 50, "views": 2000, "page_jump": 2}
        score = _calc_score(thread, "voz_f33")
        assert score > 0  # shouldn't crash


class TestSelectThreads:
    def test_selects_top_hot_and_curated(self):
        threads = [
            {"title": "Hot 1", "score": 5.0, "topic_bonus": 0.0, "url": "/t/1"},
            {"title": "Hot 2", "score": 4.0, "topic_bonus": 0.0, "url": "/t/2"},
            {"title": "Hot 3", "score": 3.0, "topic_bonus": 0.0, "url": "/t/3"},
            {"title": "Hot 4", "score": 2.0, "topic_bonus": 0.0, "url": "/t/4"},
            {"title": "Curated 1", "score": 1.5, "topic_bonus": 1.0, "url": "/t/5"},
            {"title": "Curated 2", "score": 1.0, "topic_bonus": 1.0, "url": "/t/6"},
            {"title": "Curated 3", "score": 0.8, "topic_bonus": 1.0, "url": "/t/7"},
            {"title": "Leftover", "score": 0.5, "topic_bonus": 1.0, "url": "/t/8"},
        ]
        result = _select_threads(threads)
        assert len(result) == 7
        urls = [t["url"] for t in result]
        assert "/t/1" in urls  # hot
        assert "/t/5" in urls  # curated
        assert "/t/8" not in urls  # left out

    def test_less_than_top_returns_all(self):
        threads = [
            {"title": "A", "score": 3.0, "topic_bonus": 0.0, "url": "/t/1"},
            {"title": "B", "score": 2.0, "topic_bonus": 1.0, "url": "/t/2"},
        ]
        result = _select_threads(threads)
        assert len(result) == 2

    def test_no_topic_bonus_returns_only_hot(self):
        threads = [
            {"title": "A", "score": 5.0, "topic_bonus": 0.0, "url": "/t/1"},
            {"title": "B", "score": 4.0, "topic_bonus": 0.0, "url": "/t/2"},
            {"title": "C", "score": 3.0, "topic_bonus": 0.0, "url": "/t/3"},
            {"title": "D", "score": 2.0, "topic_bonus": 0.0, "url": "/t/4"},
            {"title": "E", "score": 1.0, "topic_bonus": 0.0, "url": "/t/5"},
        ]
        result = _select_threads(threads)
        assert len(result) == 4
