import argparse
import re
import sys

import requests

from scraper import (
    J1_ONLY_PHYSICAL_STAT_KEYS,
    SEASON_GAME_KIND_IDS,
    STAT_NAME_MAP,
    _is_stat_applicable,
    _stat_keys_for_category,
    collect_appearances,
    get_players_absent_from_current_list,
    get_team_list,
)
from output import write_auto_inactive_player_csv, write_inactive_player_csv, write_stats_csv

def _normalize_year(value):
    """シーズン文字列を正規化する。全角数字は半角に変換する。

    旧実装は `re.fullmatch(r"\\d{4}", year)` だけで検証しており、全角数字
    （"２０２５"）も受理していた。その結果、URLに全角を含むことになって
    取得が静かに失敗していた。
    """
    text = str(value).strip()
    # 全角数字を半角に変換
    text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    return text


def _is_valid_year(value):
    """4桁のシーズンとして妥当かを判定する（半角数字のみ受理）。"""
    return re.fullmatch(r"[0-9]{4}", _normalize_year(value)) is not None


def prompt_input(message, default=None):
    """入力プロンプト。空入力ならデフォルトを返す。"""
    if default is not None:
        prompt = f"{message} [{default}]: "
    else:
        prompt = f"{message}: "
    value = input(prompt).strip()
    return value if value else (default if default is not None else "")

def prompt_yes_no(message, default="y"):
    """Yes/No入力を受け付ける。"""
    default = default.lower()
    suffix = "Y/n" if default == "y" else "y/N"
    while True:
        raw = input(f"{message} ({suffix}): ").strip().lower()
        if not raw:
            return default == "y"
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  入力が不正です。y か n を入力してください。")

def interactive_wizard():
    """対話式ウィザードで実行パラメータを収集する。"""
    print("\n=== Jリーグ 選手スタッツ 取得ウィザード ===")
    print("いくつか質問に答えるだけで実行できます。\n")

    # 年
    while True:
        year = prompt_input("取得したいシーズン（例: 2018 / 2025 / 2026-27）", "2026-27")
        year = _normalize_year(year)
        if year in SEASON_GAME_KIND_IDS:
            break
        print("  2018〜2026 または 2026-27 を入力してください。")

    # カテゴリ
    while True:
        category = prompt_input("カテゴリ（j1 / j2 / j3）", "j1").lower()
        if category in ("j1", "j2", "j3"):
            break
        print("  j1 / j2 / j3 のいずれかを入力してください。")

    # チーム
    print("\nチーム候補を取得しています...")
    team_candidates = get_team_list(year, category)
    if team_candidates:
        print(f"  取得できたチーム数: {len(team_candidates)}")
        print("  例: " + ", ".join(team_candidates[:10]) + (" ..." if len(team_candidates) > 10 else ""))
        print("  'all' を入力するとリーグ全体の全チームを取得します。")
    else:
        print("  チーム候補の取得に失敗しました。手入力で進めます。")

    while True:
        default_team = "shimizu"
        team = prompt_input("チームスラッグ（例: shimizu / kashima / all）", default_team).lower()
        if team == "all":
            print("  all は全チーム取得のため、10〜15分程度かかる場合があります。")
            if prompt_yes_no("実行しますか？", default="n"):
                break
            print("  チーム指定に戻ります。")
            continue
        if team_candidates and team not in team_candidates:
            print("  候補にないチームです。もう一度入力してください。")
            continue
        if team:
            break
        print("  チームを入力してください。")

    # 出力先
    output = prompt_input("保存先フォルダ", "output")

    print("\n入力内容を確認しました。これから取得を開始します。\n")
    return year, category, team, output

def main():
    parser = argparse.ArgumentParser(description="J.League Player Stats Collector")
    parser.add_argument("--season", dest="year", default="2026-27", help="取得したいシーズン（例: 2018 / 2025 / 2026-27）")
    parser.add_argument("--category", default="j1", choices=["j1", "j2", "j3"], help="カテゴリ（j1 / j2 / j3）")
    parser.add_argument("--team", default="shimizu", help="チームスラッグ（例: shimizu / kashima / all）")
    parser.add_argument("--output", default="output", help="保存先フォルダ（例: output）")
    parser.add_argument("--interactive", action="store_true", help="対話式ウィザードで実行する")
    parser.add_argument("--list-teams", action="store_true", help="チーム一覧を表示して終了する")
    parser.add_argument("--list-stats", action="store_true", help="指定カテゴリで取得可能なスタッツ項目を表示して終了する")
    parser.add_argument(
        "--list-inactive-players", action="store_true",
        help="指定シーズンの選手から現行J1/J2/J3一覧にない選手をCSV出力する",
    )
    parser.add_argument(
        "--stats", default="all",
        help="取得するスタッツ項目（カンマ区切り。デフォルト: 全項目）",
    )
    
    args = parser.parse_args()

    # CLI引数の --season も正規化する（全角数字→半角変換 + 妥当性検証）
    args.year = _normalize_year(args.year)
    selected_stats = list(STAT_NAME_MAP) if args.stats.strip().lower() == "all" else [s.strip() for s in args.stats.split(",") if s.strip()]
    unknown_stats = sorted(set(selected_stats) - set(STAT_NAME_MAP))
    if not selected_stats or unknown_stats:
        parser.error("--stats は all またはスタッツ項目名のカンマ区切りで指定してください。未知の項目: " + ", ".join(unknown_stats))
    if not (_is_valid_year(args.year) or args.year in SEASON_GAME_KIND_IDS):
        parser.error(f"--season は4桁の半角数字または 2026-27 で指定してください（入力値: {args.year!r}）")

    # 引数なし、または対話式指定ならウィザードを起動
    if args.interactive or len(sys.argv) == 1:
        year, category, team, output = interactive_wizard()
        args.year = year
        args.category = category
        args.team = team
        args.output = output

    if args.category in ("j2", "j3") and args.stats.strip().lower() != "all":
        unavailable_stats = sorted(set(selected_stats) & J1_ONLY_PHYSICAL_STAT_KEYS)
        if unavailable_stats:
            parser.error(
                f"J2/J3では取得できない項目が指定されています: {', '.join(unavailable_stats)}"
            )

    if args.list_teams:
        teams = get_team_list(args.year, args.category)
        if teams:
            print(f"チーム一覧（{args.year} {args.category}）:")
            print(", ".join(teams))
        else:
            print("チーム一覧の取得に失敗しました。")
        return

    if args.list_stats:
        print(f"取得可能なスタッツ項目（{args.category}）:")
        for stat in _stat_keys_for_category(args.category):
            print(f"  {stat}\t{STAT_NAME_MAP[stat]}")
        return

    if args.list_inactive_players:
        if args.year not in SEASON_GAME_KIND_IDS:
            parser.error("--list-inactive-players は --season 2018〜2026 または 2026-27 に対応しています")
        try:
            inactive_players = get_players_absent_from_current_list(
                args.year, args.category, args.team
            )
        except (requests.exceptions.RequestException, RuntimeError) as error:
            print(f"現行選手一覧との照合に失敗しました: {error}")
            return
        filepath = write_inactive_player_csv(
            args.output, args.year, args.category, args.team, inactive_players
        )
        print(
            f"現行J1/J2/J3選手一覧に掲載されていない選手: "
            f"{len(inactive_players)}人"
        )
        print(f"一覧CSV: {filepath}")
        if inactive_players:
            sample = ", ".join(
                f"{player['player_name']} ({player['player_id']})"
                for player in inactive_players[:10]
            )
            print(f"例: {sample}" + (" ..." if len(inactive_players) > 10 else ""))
        return

    if args.year not in SEASON_GAME_KIND_IDS:
        parser.error("スタッツ取得は --season 2018〜2026 または 2026-27 に対応しています")
    if args.team == "all":
        teams = get_team_list(args.year, args.category)
        if not teams:
            print("チーム一覧の取得に失敗したため、処理を中止します。")
            return
        print(f"{len(teams)} チームを取得します。時間がかかる場合があります。")
        if not prompt_yes_no("実行しますか？", default="n"):
            print("キャンセルしました。")
            return
    else:
        teams = [args.team]

    all_rows = []
    for current_team in teams:
        try:
            all_rows.extend(collect_appearances(
                args.year, args.category, current_team, args.output, selected_stats
            ))
        except Exception as error:
            print(f"  [チーム失敗] {current_team}: {error}")
    if not all_rows:
        print("No data collected.")
        return
    filepath = write_stats_csv(
        all_rows, args.output, args.team, args.year, args.category, selected_stats,
        STAT_NAME_MAP, J1_ONLY_PHYSICAL_STAT_KEYS, _is_stat_applicable,
    )
    print(f"\nSUCCESS: Saved to {filepath}")
    print(f"Total players: {len(all_rows)}")
    if args.year != "2018":
        inactive_rows = [row for row in all_rows if row.get("_absent_from_current_list")]
        inactive_filepath = write_auto_inactive_player_csv(
            "data", args.year, args.category, args.team, all_rows
        )
        print(f"現行Jリーグ一覧に掲載されていない選手: {len(inactive_rows)}人")
        print(f"一覧CSV: {inactive_filepath}")
    return

if __name__ == "__main__":
    main()
