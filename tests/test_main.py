"""main.py（CLI）のテスト。

ネットワークへ出ない範囲（入力の正規化・引数の検証・一覧表示）を確認する。
"""

import sys

import pytest

import main


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2025", "2025"),
        (" 2025 ", "2025"),
        ("２０２５", "2025"),  # 全角数字は半角へ
    ],
)
def test_normalize_year(raw, expected):
    assert main._normalize_year(raw) == expected


def test_is_valid_year():
    assert main._is_valid_year("2025") is True
    assert main._is_valid_year("２０２５") is True  # 正規化してから判定
    assert main._is_valid_year("20255") is False
    assert main._is_valid_year("abcd") is False


def test_cli_list_stats_for_j2_hides_physical_stats(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py", "--list-stats", "--category", "j2"])
    main.main()
    out = capsys.readouterr().out
    assert "取得可能なスタッツ項目（j2）" in out
    assert "パス成功率（％）" in out
    assert "総走行距離（km）" not in out  # J2では非公開


def test_cli_rejects_unknown_stat(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "--stats", "存在しない項目"])
    with pytest.raises(SystemExit):
        main.main()


def test_cli_rejects_physical_stat_for_j2(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "--category", "j2", "--stats", "distance"])
    with pytest.raises(SystemExit):
        main.main()
