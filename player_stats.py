"""選手一覧・チーム別ランキング・個人ページの取得と解析。

公式サイトのHTML（Next.jsのサーバーペイロード）から必要な値を取り出す。
"""

import re
import time

import requests

from http_client import REQUEST_INTERVAL, request_with_retry
from stat_definitions import (
    COMMON_PLAYER_STAT_KEYS,
    CURRENT_PLAYER_LIST_SEASON,
    GK_ONLY_STAT_KEYS,
    PLAYER_HISTORY_STAT_KEYS,
    SEASON_GAME_KIND_IDS,
    STAT_NAME_MAP,
)
from team_names import get_team_list

_current_player_ids = None
_current_player_list_error = None
_current_player_list_loaded = False


def _parse_stat_number(value):
    """詳細スタッツの表示値（単位・%付き）を数値にする。"""
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    if not match:
        return None
    number = float(match.group(0))
    return int(number) if number.is_integer() else number


def fetch_player_roster(year, category, team):
    """選手スタッツページの選手フィルターから選手IDと名前を取得する。"""
    url = (
        f"https://www.jleague.jp/{category}/stats/player/"
        f"{year}/game/search-list/?club={team}"
    )
    time.sleep(REQUEST_INTERVAL)
    response = request_with_retry(url, context=f"{team}の選手一覧")
    html = response.text

    # Next.js のサーバーペイロード内に、選手フィルターの全候補が含まれる。
    start = html.find(r'\"id\":\"player-club-')
    if start < 0:
        raise RuntimeError(f"選手一覧のデータが見つかりません (URL: {url})")
    end = html.find(r'\"id\":\"ranking-', start)
    if end < 0:
        end = min(len(html), start + 200_000)
    block = html[start:end]

    players = []
    seen = set()
    option_matches = list(re.finditer(
        r'\\"value\\":\\"(\d+)\\",\\"label\\":\\"([^"\\]+)\\"', block
    ))
    for index, match in enumerate(option_matches):
        player_id, name = match.groups()
        if player_id not in seen:
            option_end = option_matches[index + 1].start() if index + 1 < len(option_matches) else len(block)
            option = block[match.start():option_end]
            position_match = re.search(r'\\"position\\":\\"(GK|DF|MF|FW)\\"', option)
            players.append({
                "player_id": player_id,
                "player_name": name,
                "position": position_match.group(1) if position_match else "",
            })
            seen.add(player_id)
    if not players:
        raise RuntimeError(f"選手一覧を解析できません (URL: {url})")
    return players


def get_current_player_ids():
    """現行J1/J2/J3の選手IDを一度だけ取得して返す。失敗時は(None, error)。"""
    global _current_player_ids, _current_player_list_error, _current_player_list_loaded
    if not _current_player_list_loaded:
        _current_player_list_loaded = True
        try:
            player_ids = set()
            for category in ("j1", "j2", "j3"):
                players = fetch_player_roster(
                    CURRENT_PLAYER_LIST_SEASON, category, "all"
                )
                player_ids.update(player["player_id"] for player in players)
            if not player_ids:
                raise RuntimeError("現行選手一覧が空でした")
            _current_player_ids = player_ids
        except (requests.exceptions.RequestException, RuntimeError) as error:
            _current_player_list_error = str(error)
    return _current_player_ids, _current_player_list_error


def get_players_absent_from_current_list(year, category, team):
    """指定シーズン・チームの選手から現行J1/J2/J3一覧にない選手を返す。"""
    if team == "all":
        teams = get_team_list(year, category)
        if not teams:
            raise RuntimeError(f"{year}年{category}のチーム一覧を取得できません")
        players = []
        for team_slug in teams:
            players.extend(
                {**player, "_team_slug": team_slug}
                for player in fetch_player_roster(year, category, team_slug)
            )
    else:
        players = [
            {**player, "_team_slug": team}
            for player in fetch_player_roster(year, category, team)
        ]
    current_player_ids, error = get_current_player_ids()
    if current_player_ids is None:
        raise RuntimeError(f"現行選手一覧と照合できません: {error}")
    return [
        player for player in players
        if player["player_id"] not in current_player_ids
    ]


def fetch_team_stat_ranking(year, category, team, stat):
    """公式のチーム絞り込みランキングから選手別数値を取得する。"""
    url = (
        f"https://www.jleague.jp/{category}/stats/player/"
        f"{year}/{stat}/search-list/?club={team}"
    )
    time.sleep(REQUEST_INTERVAL)
    response = request_with_retry(url, context=f"{team}の{stat}ランキング")
    html = response.text
    if r'\"rankingList\"' not in html:
        raise RuntimeError(f"チーム別ランキングが見つかりません (URL: {url})")

    # 順位表の選手行は、通常 href で選手IDを持つが、過去シーズンの一部行は
    # href が省略され legacyPlayerPhotoLookup.playerId にのみIDがある。
    values = {}
    patterns = (
        re.compile(
            r'\\"playerName\\":\\".*?\\",\\"rank\\":\d+,\\"ranking\\":\d+,\\"points\\":'
            r'([0-9]+(?:\.[0-9]+)?).*?\\"playerId\\":\\"(\d+)\\"',
            re.DOTALL,
        ),
        re.compile(
            r'"playerName":".*?","rank":\d+,"ranking":\d+,"points":'
            r'([0-9]+(?:\.[0-9]+)?).*?"playerId":"(\d+)"',
            re.DOTALL,
        ),
    )
    for pattern in patterns:
        for match in pattern.finditer(html):
            value = _parse_stat_number(match.group(1))
            if value is not None:
                values[match.group(2)] = value
    return values


def _parse_player_detailed_stats(html, season):
    """個人ページのシーズン別詳細スタッツを既存の統計コードへ対応づける。"""
    game_kind_id = SEASON_GAME_KIND_IDS[season]
    all_stats_start = html.find(r'\"allYearsDetailedStats\":{')
    if all_stats_start < 0:
        raise RuntimeError("選手の詳細スタッツが見つかりません")

    season_key = f'{season[:4]}-{game_kind_id}'
    season_marker = rf'\"{season_key}\":{{'
    season_start = html.find(season_marker, all_stats_start)
    if season_start < 0:
        raise RuntimeError(f"対象シーズンの詳細スタッツが見つかりません: {season_key}")
    season_start += len(season_marker)
    # シーズンの区切りはペイロード上 `},\"2026-249\":{` のようにバックスラッシュで
    # エスケープされる。旧パターンはエスケープされていない `},"2026-249":{` しか
    # 検出できず、複数シーズンを持つ選手で常に最終シーズンの値が使われていた。
    # エスケープの有無どちらでも次シーズンの開始位置を検出できるようにする。
    next_season = re.search(r'},\\?"\d{4}-\d+\\?":\{', html[season_start:])
    season_data = html[season_start:season_start + next_season.start()] if next_season else html[season_start:]

    token_to_stat = {
        "shoot": "shoot", "saveCount": "save_count", "passCount": "pass_count",
        "longPassCount": "long_pass_count", "throughPassCount": "through_pass_count",
        "crossCount": "cross_count", "tackleCount": "tackle_count",
        "dribbleCount": "dribble_count", "airBattleWinCount": "air_battle_win_count",
    }
    subvalue_to_stat = {
        "shoot": "shoot_on_target", "saveCount": "save_rate", "passCount": "pass_rate",
        "longPassCount": "long_pass_rate", "throughPassCount": "through_pass_rate",
        "crossCount": "cross_rate", "tackleCount": "tackle_rate",
        "dribbleCount": "dribble_rate", "airBattleWinCount": "air_battle_win_rate",
    }
    stats = {key: None for key in STAT_NAME_MAP}
    for item in re.finditer(
        r'\\"id\\":\\"section-[^"\\]*?-item-\d+-([A-Za-z]\w*)\\",'
        r'\\"title\\":\\"[^"\\]*\\",\\"value\\":\\"([^"\\]*)\\"'
        r'(?:,\\"subValue\\":\\"([^"\\]*)\\")?',
        season_data,
    ):
        token, value, subvalue = item.groups()
        stat = token_to_stat.get(token)
        if stat is None:
            snake = re.sub(r"([A-Z])", r"_\1", token).lower()
            snake = snake.replace("_pg", "_per_game")
            stat = snake if snake in STAT_NAME_MAP else None
        if stat:
            stats[stat] = _parse_stat_number(value)
        sub_stat = subvalue_to_stat.get(token)
        if sub_stat and subvalue is not None:
            stats[sub_stat] = _parse_stat_number(subvalue)
    if not any(value is not None for value in stats.values()):
        raise RuntimeError(f"対象シーズンの詳細スタッツを解析できません: {season_key}")
    return stats


def fetch_player_history_stats(player_id, season):
    """個人ページの試合履歴から、指定シーズンの基本スタッツを合算する。"""
    game_kind_id = SEASON_GAME_KIND_IDS[season]
    url = f"https://www.jleague.jp/player/{player_id}/?navicode=j1#stats"
    time.sleep(REQUEST_INTERVAL)
    response = request_with_retry(
        url, context=f"選手ID {player_id} の出場履歴", timeout=(5, 45)
    )
    html = response.text

    history_match = re.search(
        r'\\"playerHistory\\":\[(.*?)\],\\"playerCareer\\"',
        html,
        re.DOTALL,
    )
    if not history_match:
        raise RuntimeError(f"選手履歴が見つかりません (URL: {url})")

    history = history_match.group(1)
    entries = list(re.finditer(
        r'\\"id\\":\\"history-[^"\\]+\\",\\"date\\":\\"[^"\\]*\\",'
        r'\\"year\\":(\d+),\\"gameKindId\\":(\d+)',
        history,
    ))
    stats = {key: 0 for key in PLAYER_HISTORY_STAT_KEYS}
    for index, entry in enumerate(entries):
        record_end = entries[index + 1].start() if index + 1 < len(entries) else len(history)
        record = history[entry.start():record_end]
        if int(entry.group(1)) != int(season[:4]) or int(entry.group(2)) != game_kind_id:
            continue
        if not re.search(r'\\"appearance\\":\\"(?:start|sub)\\"', record):
            continue
        stats["game"] += 1
        for key, field in (("time", "minutes"), ("score", "goals"), ("shoot", "shots")):
            value = re.search(rf'\\"{field}\\":(\d+)', record)
            if value:
                stats[key] += int(value.group(1))
        cards = re.search(r'\\"cards\\":\\"(\d+)/(\d+)\\"', record)
        if cards:
            stats["yellow_count"] += int(cards.group(1))
            stats["red_count"] += int(cards.group(2))
    try:
        detailed_stats = _parse_player_detailed_stats(html, season)
    except RuntimeError:
        if stats["game"] != 0:
            raise
        # 出場がない選手はシーズン詳細欄自体がない場合がある。これは取得失敗ではなく、
        # 位置に応じて該当項目を0、対象外項目を空欄として扱う。
        position = re.search(r'\\"positionText\\":\\"stats_info\.(gk|df|mf|fw)\\"', html)
        is_goalkeeper = bool(position and position.group(1) == "gk")
        detailed_stats = {key: None for key in STAT_NAME_MAP}
        for key in COMMON_PLAYER_STAT_KEYS:
            detailed_stats[key] = 0
        if is_goalkeeper:
            for key in GK_ONLY_STAT_KEYS:
                detailed_stats[key] = 0
        else:
            for key in STAT_NAME_MAP:
                if key not in GK_ONLY_STAT_KEYS:
                    detailed_stats[key] = 0
    detailed_stats["game"] = stats["game"]
    # 個人ページの詳細スタッツがある値を優先し、試合履歴由来の基本値を補完する。
    for key in ("time", "score", "shoot", "yellow_count", "red_count"):
        if detailed_stats[key] is None:
            detailed_stats[key] = stats[key]
    return detailed_stats
