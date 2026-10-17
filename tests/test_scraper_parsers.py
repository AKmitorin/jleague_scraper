"""scraper.py の「解析」まわりのテスト。

Jリーグ公式サイトのHTMLはちょっとした改修で構造が変わり、しかもその変化に
気づきにくい（気づくとCSVが空欄だらけになる）。そこで、実際のページから
切り出した fixtures/ のHTMLを入力にして、解析結果が期待どおりかを固定する。
"""

import pytest

import scraper
from conftest import load_fixture, make_fake_response


# ---------------------------------------------------------------------------
# 文字列→数値の変換
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("12", 12),
        ("1,234", 1234),        # カンマ区切り
        ("12.5", 12.5),         # 小数
        ("60.4%", 60.4),        # 半角パーセント
        ("60.4％", 60.4),       # 全角パーセント
        ("-", None),            # 未取得・対象外
        ("", None),
        ("abc", None),
    ],
)
def test_parse_stat_number(raw, expected):
    assert scraper._parse_stat_number(raw) == expected


# ---------------------------------------------------------------------------
# ポジションごとの項目の取捨
# ---------------------------------------------------------------------------
def test_is_stat_applicable_by_position():
    # GK専用項目は GK のみ、それ以外のポジションでは対象外
    assert scraper._is_stat_applicable("save_count", "GK") is True
    assert scraper._is_stat_applicable("save_count", "FW") is False
    # 全ポジション共通の項目
    assert scraper._is_stat_applicable("game", "GK") is True
    assert scraper._is_stat_applicable("game", "MF") is True
    # ポジション不明（空文字）は安全側に倒して対象扱い
    assert scraper._is_stat_applicable("save_count", "") is True


def test_stat_keys_for_category_excludes_physical_for_j2_j3():
    assert set(scraper._stat_keys_for_category("j1")) == set(scraper.STAT_NAME_MAP)
    assert set(scraper._stat_keys_for_category("j2")) == (
        set(scraper.STAT_NAME_MAP) - scraper.J1_ONLY_PHYSICAL_STAT_KEYS
    )
    assert "distance" not in scraper._stat_keys_for_category("j3")


# ---------------------------------------------------------------------------
# 選手一覧（フィルターの選択肢）の解析
# ---------------------------------------------------------------------------
def test_fetch_player_roster(monkeypatch):
    html = load_fixture("player_roster_shimizu.html")
    monkeypatch.setattr(
        scraper, "_request_with_retry", lambda *args, **kwargs: make_fake_response(html)
    )

    players = scraper._fetch_player_roster("2026-27", "j1", "shimizu")

    assert len(players) == 54
    assert players[0] == {
        "player_id": "1658196",
        "player_name": "山田 竜之介",
        "position": "GK",
    }
    # 同じ選手IDが二重に出てこない
    ids = [player["player_id"] for player in players]
    assert len(ids) == len(set(ids))
    assert {player["position"] for player in players} == {"GK", "DF", "MF", "FW"}


def test_fetch_player_roster_raises_on_unexpected_html(monkeypatch):
    monkeypatch.setattr(
        scraper,
        "_request_with_retry",
        lambda *args, **kwargs: make_fake_response("<html>想定外のページ</html>"),
    )
    with pytest.raises(RuntimeError):
        scraper._fetch_player_roster("2026-27", "j1", "shimizu")


# ---------------------------------------------------------------------------
# チーム別ランキングの解析
# ---------------------------------------------------------------------------
def test_fetch_team_stat_ranking(monkeypatch):
    html = load_fixture("team_ranking_score_shimizu.html")
    monkeypatch.setattr(
        scraper, "_request_with_retry", lambda *args, **kwargs: make_fake_response(html)
    )

    values = scraper._fetch_team_stat_ranking("2026-27", "j1", "shimizu", "score")

    assert values["1503986"] == 2
    assert all(isinstance(value, (int, float)) for value in values.values())


def test_fetch_team_stat_ranking_raises_when_marker_missing(monkeypatch):
    monkeypatch.setattr(
        scraper,
        "_request_with_retry",
        lambda *args, **kwargs: make_fake_response("<html></html>"),
    )
    with pytest.raises(RuntimeError):
        scraper._fetch_team_stat_ranking("2026-27", "j1", "shimizu", "score")


# ---------------------------------------------------------------------------
# チーム名（スラッグ→正式名）の取得
# ---------------------------------------------------------------------------
def test_team_name_map(monkeypatch):
    html = load_fixture("team_options_j1.html")

    class FakeSession:
        def get(self, url, **kwargs):
            return make_fake_response(html)

    monkeypatch.setattr(scraper, "_get_session", lambda: FakeSession())

    name_map = scraper._team_name_map("2026-27", "j1")

    assert name_map["kashima"] == "鹿島アントラーズ"
    assert name_map["shimizu"] == "清水エスパルス"
    assert "all" not in name_map  # 「全クラブ」の選択肢は除外される


# ---------------------------------------------------------------------------
# 個人ページのシーズン別詳細スタッツの解析
# ---------------------------------------------------------------------------
def test_parse_player_detailed_stats_uses_requested_season():
    """指定シーズンの値だけを返す（他シーズンの値が混ざらない）こと。

    かつてはシーズンの区切りを検出できず、複数シーズンを持つ選手では
    常に最後のシーズンの値が使われていた。
    """
    html = load_fixture("player_1503986.html")

    stats_2026 = scraper._parse_player_detailed_stats(html, "2026-27")
    stats_2025 = scraper._parse_player_detailed_stats(html, "2025")

    assert stats_2026["time"] == 499
    assert stats_2025["time"] == 1468
    # シーズンが違えば結果も違う = 区切りを正しく見ている
    assert stats_2026 != stats_2025


def test_fetch_player_history_stats(monkeypatch):
    html = load_fixture("player_1503986.html")
    monkeypatch.setattr(
        scraper, "_request_with_retry", lambda *args, **kwargs: make_fake_response(html)
    )

    stats = scraper._fetch_player_history_stats("1503986", "2026-27")

    # 出場試合数は試合履歴から、詳細スタッツは個人ページから補完される
    assert stats["game"] == 8
    assert stats["time"] == 499
    assert stats["score"] == 2
    assert stats["shoot"] == 15
