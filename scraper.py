"""選手スタッツ取得の集計（オーケストレーション）。

サイトから取得・解析する処理は player_stats / team_names、HTTPは http_client、
項目定義は stat_definitions、CSV出力は output が担当する。ここはそれらを
組み合わせて1チーム分の行データを作るだけにしている。
"""

import os

import requests

from output import write_stat_failure_log
from player_stats import (
    fetch_player_history_stats,
    fetch_player_roster,
    fetch_team_stat_ranking,
    get_current_player_ids,
)
from stat_definitions import (
    J1_ONLY_PHYSICAL_STAT_KEYS,
    SEASON_GAME_KIND_IDS,
    STAT_NAME_MAP,
    is_stat_applicable,
)
from team_names import get_team_name


def collect_appearances(year, category, team, output_dir="output", selected_stats=None):
    """公式ページの選手一覧とスタッツから選手別データを集計する。

    2018年は選手個人ページの詳細スタッツがないため、チーム別ランキングのみを使う。
    """
    if year not in SEASON_GAME_KIND_IDS:
        raise ValueError("スタッツ取得は 2018〜2026 または 2026-27 に対応しています")

    ranking_only = year == "2018"

    players = fetch_player_roster(year, category, team)
    print(f"選手一覧を取得しました: {len(players)}人")
    current_player_ids = None
    if not ranking_only:
        current_player_ids, current_list_error = get_current_player_ids()
        if current_player_ids is None:
            print(
                "警告: 現行J1/J2/J3選手一覧と照合できないため、"
                f"全選手の個人ページを取得します: {current_list_error}"
            )
        else:
            absent_count = sum(
                player["player_id"] not in current_player_ids for player in players
            )
            print(f"現行J1/J2/J3選手一覧に掲載なし: {absent_count}人")
    # チームで絞った公式ランキングを使うことで、移籍前後を分けたチーム在籍時の値を取る。
    # ポジションに存在する項目だけ取得し、同じチームの選手間ではランキングを共有する。
    selected_stats = set(selected_stats or STAT_NAME_MAP)
    applicable_stats = {
        stat for stat in STAT_NAME_MAP
        if stat in selected_stats
        if any(is_stat_applicable(stat, p.get("position", "")) for p in players)
        and (category == "j1" or stat not in J1_ONLY_PHYSICAL_STAT_KEYS)
    }
    team_rankings = {}
    ranking_errors = {}
    for stat in STAT_NAME_MAP:
        if stat not in applicable_stats:
            continue
        try:
            team_rankings[stat] = fetch_team_stat_ranking(year, category, team, stat)
        except (requests.exceptions.RequestException, RuntimeError) as e:
            ranking_errors[stat] = str(e)
            print(f"注意: {team} の {STAT_NAME_MAP[stat]}を取得できません: {e}")

    rows = []
    errors = []
    for index, player in enumerate(players, start=1):
        absent_from_current_list = (
            not ranking_only
            and current_player_ids is not None
            and player["player_id"] not in current_player_ids
        )
        task = (
            "スタッツを集計中" if ranking_only
            else "個人ページを省略（現行一覧になし）" if absent_from_current_list
            else "出場履歴を取得中"
        )
        print(f"[{index}/{len(players)}] {player['player_name']} の{task}")
        player_url = f"https://www.jleague.jp/player/{player['player_id']}/?navicode=j1#stats"
        if ranking_only or absent_from_current_list:
            player_stats = {
                key: None for key in STAT_NAME_MAP
            }
            # 現行一覧にない選手は「意図的に個人ページを省略」しているだけで、取得失敗ではない。
            # そのため失敗ログ（およびエラーCSV）には出さず、未取得は通常CSVの "-" として残す。
            fetch_error = None
            player_page_failed = absent_from_current_list
        else:
            try:
                player_stats = fetch_player_history_stats(player["player_id"], year)
                fetch_error = None
                player_page_failed = False
            except (requests.exceptions.RequestException, RuntimeError) as e:
                player_stats = {
                    # 取得できなかった値を実績ゼロと区別する。ランキングで
                    # 後から取得できた項目は、この None が実値に置き換わる。
                    key: None
                    for key in STAT_NAME_MAP
                }
                fetch_error = str(e)
                player_page_failed = True

        # 成功した公式チーム別ランキングは、個人ページのシーズン合計より優先する。
        # 個人ページの取得にも失敗した場合、ランキングに選手がいない値は未取得のままにする。
        for stat, ranking in team_rankings.items():
            if is_stat_applicable(stat, player.get("position", "")):
                player_id = player["player_id"]
                if player_id in ranking:
                    player_stats[stat] = ranking[player_id]
                elif ranking_only or not player_page_failed:
                    # ページを正常取得できた場合（またはランキングのみで集計する2018年）は、
                    # ランキングに載らないことを0として扱える。
                    player_stats[stat] = 0
        if fetch_error:
            required_stats = {
                stat for stat in STAT_NAME_MAP
                if stat in selected_stats
                if is_stat_applicable(stat, player.get("position", ""))
                and (category == "j1" or stat not in J1_ONLY_PHYSICAL_STAT_KEYS)
            }
            missing_stats = sorted(
                stat for stat in required_stats if player_stats.get(stat) is None
            )
            if missing_stats:
                missing_names = ", ".join(STAT_NAME_MAP[stat] for stat in missing_stats)
                errors.append((
                    player["player_id"], player["player_name"],
                    f"個人ページ取得失敗（{fetch_error}）。ランキングにもデータなし: {missing_names}",
                ))
        if ranking_errors:
            for stat, error in ranking_errors.items():
                if stat in selected_stats and is_stat_applicable(stat, player.get("position", "")):
                    errors.append((
                        player["player_id"], player["player_name"],
                        f"{STAT_NAME_MAP[stat]}のチーム別ランキング取得失敗: {error}",
                    ))
        row = {
            "player_id": player["player_id"],
            "player_url": player_url,
            "player_name": player["player_name"],
            "team_name": get_team_name(year, category, team),
            "_position": player.get("position", ""),
            "_team_slug": team,
            "_absent_from_current_list": absent_from_current_list,
        }
        row.update({key: value for key, value in player_stats.items() if key in selected_stats})
        if category in ("j2", "j3"):
            for stat in J1_ONLY_PHYSICAL_STAT_KEYS:
                row[stat] = None
        rows.append(row)

    if errors:
        print(f"注意: {len(errors)}件のスタッツ取得失敗があります:")
        for player_id, name, error in errors:
            print(f"  {name} ({player_id}): {error}")
        error_rows = []
        for player_id, name, error in errors:
            player_url = f"https://www.jleague.jp/player/{player_id}/?navicode=j1#stats"
            error_rows.append((team, name, player_url, "選手ページ/チーム別ランキング", error))
        write_stat_failure_log(output_dir, year, category, team, error_rows)
        if error_rows:
            print(f"取得失敗ログ: {os.path.join(output_dir, f'stats_{team}_{year}_{category}_errors.csv')}")
    else:
        # 前回実行の失敗ログが残らないよう、既存ファイルがあれば空に更新する。
        write_stat_failure_log(output_dir, year, category, team, [])
    return rows
