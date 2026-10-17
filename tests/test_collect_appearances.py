"""collect_appearances（1チーム分の集計）のテスト。

ここは「どの値がどこから来るか」を決める中心ロジックで、分岐が多い:
  - 2018年はチーム別ランキングだけを使う
  - 個人ページよりチーム別ランキングを優先する
  - 現行一覧にない選手は個人ページを取りに行かない
  - 取得失敗は失敗ログ用に集める
外部通信はすべて差し替え、値の出どころと失敗の記録を確認する。
"""

import pytest

import scraper


def _player(player_id="p1", name="テスト 太郎", position="MF"):
    return {"player_id": player_id, "player_name": name, "position": position}


class CollectorStub:
    """collect_appearances が呼ぶ依存をまとめて差し替えるスタブ。"""

    def __init__(self):
        self.current_ids = set()      # get_current_player_ids が返すID
        self.current_error = None     # 一覧取得に失敗した場合のメッセージ
        self.rankings = {}            # stat -> {player_id: value}
        self.ranking_failures = {}    # stat -> 例外
        self.history = {}             # player_id -> dict または 例外
        self.team_name = "テストFC"
        self.calls = {"ranking": [], "history": [], "failure_log": []}

    def install(self, monkeypatch, players):
        monkeypatch.setattr(scraper, "fetch_player_roster", lambda *a, **k: players)
        monkeypatch.setattr(
            scraper, "get_current_player_ids", lambda: (self.current_ids, self.current_error)
        )
        monkeypatch.setattr(scraper, "fetch_team_stat_ranking", self._ranking)
        monkeypatch.setattr(scraper, "fetch_player_history_stats", self._history)
        monkeypatch.setattr(scraper, "get_team_name", lambda *a, **k: self.team_name)
        monkeypatch.setattr(scraper, "write_stat_failure_log", self._failure_log)

    def _ranking(self, year, category, team, stat):
        self.calls["ranking"].append(stat)
        if stat in self.ranking_failures:
            raise self.ranking_failures[stat]
        return dict(self.rankings.get(stat, {}))

    def _history(self, player_id, season):
        self.calls["history"].append(player_id)
        outcome = self.history.get(player_id)
        if isinstance(outcome, Exception):
            raise outcome
        return dict(outcome or {})

    def _failure_log(self, output_dir, year, category, team, failures):
        self.calls["failure_log"].append(list(failures))
        return "ログのパス"


# ---------------------------------------------------------------------------
# 引数の検証
# ---------------------------------------------------------------------------
def test_collect_appearances_rejects_unsupported_season():
    with pytest.raises(ValueError):
        scraper.collect_appearances("2017", "j1", "shimizu")


# ---------------------------------------------------------------------------
# 2018年: ランキングのみ
# ---------------------------------------------------------------------------
def test_collect_appearances_2018_uses_rankings_only(monkeypatch, tmp_path):
    stub = CollectorStub()
    stub.rankings = {"game": {"p1": 10}}
    # もし個人ページを取りに行ったら気づけるようにしておく
    stub.history["p1"] = RuntimeError("個人ページは取得しないはず")
    stub.install(monkeypatch, [_player()])

    rows = scraper.collect_appearances(
        "2018", "j1", "shimizu", str(tmp_path), ["game", "score"]
    )

    assert len(rows) == 1
    assert rows[0]["game"] == 10
    assert rows[0]["score"] == 0              # ランキングに無い = 出場なし
    assert rows[0]["_absent_from_current_list"] is False
    assert stub.calls["history"] == []        # 個人ページは取得しない
    assert stub.calls["failure_log"] == [[]]  # 失敗なし


def test_collect_appearances_skips_gk_stats_for_outfield_player(monkeypatch, tmp_path):
    stub = CollectorStub()
    stub.history["p1"] = {}
    stub.install(monkeypatch, [_player(position="FW")])

    scraper.collect_appearances("2025", "j1", "shimizu", str(tmp_path), ["save_count"])

    # FWにGK専用項目は取得しない
    assert stub.calls["ranking"] == []


# ---------------------------------------------------------------------------
# 通常シーズン: ランキング優先
# ---------------------------------------------------------------------------
def test_collect_appearances_prefers_ranking_over_player_page(monkeypatch, tmp_path):
    stub = CollectorStub()
    stub.current_ids = {"p1"}
    stub.rankings = {"game": {"p1": 5}, "score": {}}  # score はランキングに無い
    stub.history["p1"] = {"game": 3, "score": 1}
    stub.install(monkeypatch, [_player()])

    rows = scraper.collect_appearances(
        "2025", "j1", "shimizu", str(tmp_path), ["game", "score"]
    )

    assert rows[0]["game"] == 5    # ランキングの値を優先
    assert rows[0]["score"] == 0   # ランキングに無い = 0（個人ページの1は使わない）
    assert stub.calls["history"] == ["p1"]
    assert stub.calls["failure_log"] == [[]]


def test_collect_appearances_sets_row_metadata(monkeypatch, tmp_path):
    stub = CollectorStub()
    stub.current_ids = {"p1"}
    stub.history["p1"] = {"game": 2}
    stub.install(monkeypatch, [_player()])

    rows = scraper.collect_appearances("2025", "j1", "shimizu", str(tmp_path), ["game"])

    assert rows[0]["team_name"] == "テストFC"
    assert rows[0]["player_id"] == "p1"
    assert rows[0]["player_url"] == "https://www.jleague.jp/player/p1/?navicode=j1#stats"


# ---------------------------------------------------------------------------
# 現行一覧にない選手: 個人ページを省略
# ---------------------------------------------------------------------------
def test_collect_appearances_skips_personal_page_for_absent_player(monkeypatch, tmp_path):
    stub = CollectorStub()
    stub.current_ids = {"someone-else"}
    stub.rankings = {"game": {"p1": 4}}
    stub.history["p1"] = RuntimeError("個人ページは取得しないはず")
    stub.install(monkeypatch, [_player()])

    rows = scraper.collect_appearances("2025", "j1", "shimizu", str(tmp_path), ["game"])

    assert rows[0]["_absent_from_current_list"] is True
    assert rows[0]["game"] == 4
    assert stub.calls["history"] == []
    assert stub.calls["failure_log"] == [[]]  # 意図的な省略は失敗ログに出さない


def test_collect_appearances_absent_player_without_ranking_stays_unknown(monkeypatch, tmp_path):
    stub = CollectorStub()
    stub.current_ids = {"someone-else"}
    stub.rankings = {}  # どこにも載っていない
    stub.install(monkeypatch, [_player()])

    rows = scraper.collect_appearances("2025", "j1", "shimizu", str(tmp_path), ["score"])

    assert rows[0]["score"] is None           # 省略したので0とはみなさない
    assert stub.calls["history"] == []
    # 取得失敗ではないので、失敗ログには出さない
    assert stub.calls["failure_log"] == [[]]


# ---------------------------------------------------------------------------
# 取得失敗の記録
# ---------------------------------------------------------------------------
def test_collect_appearances_logs_player_page_failure(monkeypatch, tmp_path):
    stub = CollectorStub()
    stub.current_ids = {"p1"}
    stub.rankings = {"assist": {}}
    stub.history["p1"] = RuntimeError("取得失敗")
    stub.install(monkeypatch, [_player()])

    rows = scraper.collect_appearances("2025", "j1", "shimizu", str(tmp_path), ["assist"])

    assert rows[0]["assist"] is None
    failures = stub.calls["failure_log"][0]
    assert len(failures) == 1
    assert "個人ページ取得失敗" in failures[0][4]


def test_collect_appearances_logs_ranking_failure(monkeypatch, tmp_path):
    stub = CollectorStub()
    stub.current_ids = {"p1"}
    stub.ranking_failures = {"game": RuntimeError("ランキング落ち")}
    stub.history["p1"] = {"game": 7}
    stub.install(monkeypatch, [_player()])

    rows = scraper.collect_appearances("2025", "j1", "shimizu", str(tmp_path), ["game"])

    assert rows[0]["game"] == 7  # 個人ページの値は残る
    failures = stub.calls["failure_log"][0]
    assert any("チーム別ランキング取得失敗" in failure[4] for failure in failures)


# ---------------------------------------------------------------------------
# J2/J3: フィジカル系は空欄
# ---------------------------------------------------------------------------
def test_collect_appearances_j2_blanks_physical_stats(monkeypatch, tmp_path):
    stub = CollectorStub()
    stub.current_ids = {"p1"}
    stub.history["p1"] = {"game": 1}
    stub.install(monkeypatch, [_player()])

    rows = scraper.collect_appearances(
        "2025", "j2", "shimizu", str(tmp_path), ["game", "distance"]
    )

    assert rows[0]["distance"] is None
    assert "distance" not in stub.calls["ranking"]  # J2では取得しない


# ---------------------------------------------------------------------------
# 選手一覧の取得失敗はそのまま伝わる（呼び出し側でチーム単位に処理する）
# ---------------------------------------------------------------------------
def test_collect_appearances_propagates_roster_error(monkeypatch, tmp_path):
    def boom(*args, **kwargs):
        raise RuntimeError("選手一覧の取得に失敗")

    monkeypatch.setattr(scraper, "fetch_player_roster", boom)
    with pytest.raises(RuntimeError):
        scraper.collect_appearances("2025", "j1", "shimizu", str(tmp_path), ["game"])
