"""output.py（CSV書き出し）のテスト。

CSVは利用者が直接Excelで開く成果物なので、「列の並び」「未取得の表し方」
「BOM付きUTF-8」といった見た目を固定しておく。
"""

import csv
import os

import output
import scraper


def _read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.reader(handle))


def test_prepare_output_path_creates_directory(tmp_path):
    path = output.prepare_output_path(str(tmp_path / "nested" / "deep"), "x.csv")
    assert (tmp_path / "nested" / "deep").is_dir()
    assert path.endswith("x.csv")


def test_write_stats_csv_headers_and_missing_values(tmp_path):
    rows = [
        {
            "player_url": "https://www.jleague.jp/player/1/",
            "player_name": "テスト 太郎",
            "team_name": "テストFC",
            "_position": "FW",
            "game": 5,
            "assist": None,      # 対象ポジションだが未取得 → "-"
            "save_count": None,  # GK専用項目 → 空欄
            "distance": None,    # J2では非公開 → 空欄
        }
    ]
    filepath = output.write_stats_csv(
        rows,
        str(tmp_path),
        "shimizu",
        "2025",
        "j2",
        ["game", "assist", "save_count", "distance"],
        scraper.STAT_NAME_MAP,
        scraper.J1_ONLY_PHYSICAL_STAT_KEYS,
        scraper._is_stat_applicable,
    )

    data = _read_csv(filepath)
    assert data[0] == [
        "選手URL", "選手名", "チーム名",
        "出場試合数（試合）", "アシスト総数（回）", "セーブ総数（回）", "総走行距離（km）",
    ]
    assert data[1][2] == "テストFC"
    assert data[1][3] == "5"
    assert data[1][4] == "-"
    assert data[1][5] == ""
    assert data[1][6] == ""

    # Excelで文字化けしないよう BOM 付き UTF-8 で保存される
    with open(filepath, "rb") as handle:
        assert handle.read(3) == b"\xef\xbb\xbf"


def test_write_stats_csv_j1_marks_missing_physical_as_dash(tmp_path):
    rows = [
        {
            "player_url": "https://www.jleague.jp/player/2/",
            "player_name": "テスト 次郎",
            "team_name": "テストFC",
            "_position": "MF",
            "distance": None,
        }
    ]
    filepath = output.write_stats_csv(
        rows,
        str(tmp_path),
        "shimizu",
        "2025",
        "j1",
        ["distance"],
        scraper.STAT_NAME_MAP,
        scraper.J1_ONLY_PHYSICAL_STAT_KEYS,
        scraper._is_stat_applicable,
    )
    assert _read_csv(filepath)[1][3] == "-"


def test_write_inactive_player_csv(tmp_path):
    players = [
        {
            "player_id": "123",
            "player_name": "過去 太郎",
            "position": "MF",
            "_team_slug": "shimizu",
        }
    ]
    filepath = output.write_inactive_player_csv(
        str(tmp_path), "2020", "j1", "shimizu", players
    )
    assert os.path.basename(filepath) == "players_not_current_shimizu_2020_j1.csv"

    data = _read_csv(filepath)
    assert data[0] == [
        "対象シーズン", "対象カテゴリ", "対象チーム", "選手ID", "選手名",
        "ポジション", "選手URL", "現行J1/J2/J3一覧",
    ]
    assert data[1] == [
        "2020", "j1", "shimizu", "123", "過去 太郎", "MF",
        "https://www.jleague.jp/player/123/", "掲載なし",
    ]


def test_write_auto_inactive_player_csv_filters_flagged_rows(tmp_path):
    rows = [
        {"player_id": "1", "player_name": "A", "position": "MF", "_absent_from_current_list": True},
        {"player_id": "2", "player_name": "B", "position": "MF", "_absent_from_current_list": False},
    ]
    filepath = output.write_auto_inactive_player_csv(
        str(tmp_path), "2020", "j1", "shimizu", rows
    )
    data = _read_csv(filepath)
    assert len(data) == 2  # ヘッダ + 該当した1人だけ
    assert data[1][3] == "1"


def test_write_stat_failure_log(tmp_path):
    filepath = output.write_stat_failure_log(
        str(tmp_path),
        "2025",
        "j1",
        "shimizu",
        [("shimizu", "太郎", "https://example.com/p", "項目", "理由")],
    )
    data = _read_csv(filepath)
    assert data[0] == ["チーム", "選手名", "選手URL", "項目", "理由"]
    assert data[1][0] == "shimizu"


def test_write_stat_failure_log_without_failures_creates_nothing(tmp_path):
    result = output.write_stat_failure_log(str(tmp_path), "2025", "j1", "shimizu", [])
    assert result is None
    assert not (tmp_path / "stats_shimizu_2025_j1_errors.csv").exists()


def test_write_stat_failure_log_truncates_previous_log(tmp_path):
    output.write_stat_failure_log(
        str(tmp_path), "2025", "j1", "shimizu", [("a", "b", "c", "d", "e")]
    )
    filepath = output.write_stat_failure_log(str(tmp_path), "2025", "j1", "shimizu", [])
    # 前回の失敗が残らないよう、ヘッダだけに上書きされる
    assert len(_read_csv(filepath)) == 1
