import csv
import json
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

# HTTP request timeout (connect, read) in seconds
REQUEST_TIMEOUT = (5, 20)

# リトライ対象とするリトライ回数
MAX_RETRIES = 3

# リトライ間の基本待機秒数（指数バックオフ）
RETRY_BACKOFF_BASE = 2

# サーバー負荷軽減のため、リクエスト間の固定待機秒数
REQUEST_INTERVAL = 0.5

# 同一セッションでリクエストを実行するための Session
_session = None


def _get_session():
    """requests.Session をシングルトンで取得する。接続再利用によりTLSハンドシェイクを省略できる。"""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "ja,en;q=0.8",
        })
    return _session

# 統計項目のコードから日本語名（単位）へのマッピング
STAT_NAME_MAP = {
    "game": "出場試合数（試合）",
    "time": "出場時間（分）",
    "shoot": "シュート総数（回）",
    "shoot_per_game": "1試合平均シュート数（回）",
    "shoot_on_target": "枠内シュート総数（回）",
    "shoot_rate": "シュート決定率（％）",
    "suffer_shoot": "被シュート総数（回）",
    "suffer_shoot_on_target": "被枠内シュート総数（回）",
    "score": "得点（点）",
    "fk_score": "FK得点数（点）",
    "pk_score": "PK得点数（点）",
    "left_foot_score": "左足得点数（点）",
    "right_foot_score": "右足得点数（点）",
    "head_score": "ヘディング得点数（点）",
    "other_type_score": "その他部位得点数（点）",
    "expected_goals": "ゴール期待値",
    "expected_goals_excl_pk": "ゴール期待値 ※PKを除く",
    "expected_goals_diff": "得点数とゴール期待値の差分",
    "assist": "アシスト総数（回）",
    "lost": "失点総数（点）",
    "play_count": "プレー総数（回）",
    "play_count_per_game": "1試合平均プレー数（回）",
    "pass_count": "パス総数（回）",
    "pass_count_per_game": "1試合平均パス数（回）",
    "pass_rate": "パス成功率（％）",
    "opponent_area_pass_count": "敵陣パス数（回）",
    "opponent_area_pass_rate": "敵陣パス成功率（％）",
    "opponent_area_pass_count_per_game": "1試合平均敵陣パス数（回）",
    "own_area_pass_count": "自陣パス数（回）",
    "own_area_pass_rate": "自陣パス成功率（％）",
    "own_area_pass_count_per_game": "1試合平均自陣パス数（回）",
    "long_pass_count": "ロングパス総数（回）",
    "long_pass_rate": "ロングパス成功率（％）",
    "long_pass_count_per_game": "1試合平均ロングパス数（回）",
    "dribble_count": "ドリブル総数（回）",
    "dribble_rate": "ドリブル成功率（％）",
    "through_pass_count": "スルーパス総数（回）",
    "through_pass_rate": "スルーパス成功率（％）",
    "cross_count": "クロス総数（回）",
    "cross_rate": "クロス成功率（％）",
    "cross_count_per_game": "1試合平均クロス数（回）",
    "clear_count": "クリア総数（回）",
    "tackle_count": "タックル総数（回）",
    "tackle_rate": "タックル成功率（％）",
    "tackle_count_per_game": "1試合平均タックル数（回）",
    "block_count": "ブロック総数（回）",
    "intercept_count": "インターセプト総数（回）",
    "intercept_count_per_game": "1試合平均インターセプト数（回）",
    "air_battle_win_count": "空中戦勝利数（回）",
    "air_battle_win_rate": "空中戦勝率（％）",
    "foul_count": "ファウル総数（回）",
    "suffer_foul_count": "被ファウル総数（回）",
    "yellow_count": "警告数（回）",
    "red_count": "退場数（回）",
    "chance_create": "チャンスクリエイト総数（回）",
    "chance_create_per_game": "1試合平均チャンスクリエイト数（回）",
    "duels_won": "デュエル勝利総数（回）",
    "recovery_count": "こぼれ球奪取総数（回）",
    "fk": "FK総数（回）",
    "ck": "CK総数（回）",
    "save_count": "セーブ総数（回）",
    "save_rate": "セーブ率（％）",
    "save_count_per_game": "1試合平均セーブ数（回）",
    "save_rate_in_pa": "PA内シュートセーブ率（％）",
    "save_rate_out_pa": "PA外シュートセーブ率（％）",
    "save_catch_rate_in_pa": "PA内シュートキャッチ率（％）",
    "save_catch_rate_out_pa": "PA外シュートキャッチ率（％）",
    "cross_catch_rate": "クロスキャッチ率（％）",
    "save_punch_rate_in_pa": "PA内シュートパンチング率（％）",
    "save_punch_rate_out_pa": "PA外シュートパンチング率（％）",
    "cross_punch_rate": "クロスパンチング率（％）",
    "clean_sheet": "クリーンシート総数（回）",
    "distance": "総走行距離（km）",
    "top_speed": "トップスピード（km/h）",
    "sprint": "総スプリント回数（回）",
    "at_sprint": "Atスプリント回数（回）",
    "mt_sprint": "Mtスプリント回数（回）",
    "dt_sprint": "Dtスプリント回数（回）",
    "possession_distance": "ポゼッション時の走行距離（km）",
    "possession_sprint": "ポゼッション時のスプリント回数（回）",
    "un_possession_distance": "被ポゼッション時の走行距離（km）",
    "un_possession_sprint": "被ポゼッション時のスプリント回数（回）",
}

# J2・J3の公式選手スタッツでは提供されないフィジカル系項目。
J1_ONLY_PHYSICAL_STAT_KEYS = {
    "distance", "top_speed", "sprint", "at_sprint", "mt_sprint", "dt_sprint",
    "possession_distance", "possession_sprint",
    "un_possession_distance", "un_possession_sprint",
}


def _stat_keys_for_category(category):
    if category in ("j2", "j3"):
        return [key for key in STAT_NAME_MAP if key not in J1_ONLY_PHYSICAL_STAT_KEYS]
    return list(STAT_NAME_MAP)

def get_team_list(year, category):
    """現行の公式スタッツページからクラブ選択肢のスラッグ一覧を取得する。"""
    url = f"https://www.jleague.jp/{category}/stats/player/{year}/score/search-list/"
    try:
        response = _get_session().get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        # 現行サイトは select 要素ではなく、Next.js の RSC ペイロードに
        # id="club" の選択肢を JSON として埋め込んでいる。
        payload = response.text.replace(r'\"', '"')
        club_options = re.search(
            r'"id":"club".*?"id":"club-all".*?"options":(\[.*?\])',
            payload,
            re.DOTALL,
        )
        if club_options:
            options = json.loads(club_options.group(1))
            teams = [option.get("value", "") for option in options]
            teams = [team for team in teams if team and team != "all"]
            if teams:
                return teams

        print(
            f"警告: クラブ一覧データが見つかりません (URL: {url})。"
            "サイトの構造変更が考えられます。"
        )
        return []
    except requests.exceptions.RequestException as e:
        # ネットワークエラーとHTTPエラーを区別して報告する
        print(f"チーム一覧の取得に失敗しました（ネットワークまたはHTTPエラー）: {e}")
        return []
    except Exception as e:
        print(f"チーム一覧の解析中に予期しないエラーが発生しました: {e}")
        return []

def _parse_retry_after(headers):
    """Retry-Afterヘッダの値から待機秒数を返す。

    秒数形式（"120"）とHTTP-date形式（"Wed, 21 Oct 2026 07:28:00 GMT"）の両方に対応する。
    パースできない場合はNoneを返す（呼び出し側でフォールバックする）。
    """
    retry_after = headers.get("Retry-After")
    if not retry_after:
        return None

    retry_after = retry_after.strip()

    # 秒数形式
    if retry_after.isdigit():
        return int(retry_after)

    # HTTP-date形式
    try:
        dt = parsedate_to_datetime(retry_after)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        seconds = (dt - datetime.now(timezone.utc)).total_seconds()
        # すでに過ぎている場合は即リトライしてよい
        return max(0, int(seconds))
    except (TypeError, ValueError, OverflowError):
        return None


def _request_with_retry(url, context="", max_retries=MAX_RETRIES, timeout=REQUEST_TIMEOUT):
    """GETリクエストをリトライ付きで実行する。成功時はレスポンスを返す。

    リトライ対象:
      - 429 Too Many Requests（Retry-Afterヘッダがあれば従う）
      - 5xx サーバーエラー（指数バックオフ）
      - タイムアウト / 接続エラー（指数バックオフ）

    旧実装には「全試行がタイムアウトだと response が未代入のまま参照され
    UnboundLocalError になる」「429のレスポンスをデータとして解析する」といった
    不具合があった。ループが確実に response を返すよう構造を改めた。
    """
    session = _get_session()
    last_error = None

    for attempt in range(1, max_retries + 1):
        exhausted = attempt >= max_retries
        try:
            response = session.get(url, timeout=timeout)

            # 429 Too Many Requests
            if response.status_code == 429:
                if exhausted:
                    last_error = "429 Too Many Requests（リトライ上限に到達）"
                    break
                wait_seconds = _parse_retry_after(response.headers)
                if wait_seconds is None:
                    wait_seconds = RETRY_BACKOFF_BASE ** attempt
                print(
                    f"  [429] {context} レート制限。{wait_seconds}秒待機して再試行します "
                    f"({attempt}/{max_retries})"
                )
                time.sleep(wait_seconds)
                continue

            # 5xx サーバーエラー
            if 500 <= response.status_code < 600:
                if exhausted:
                    last_error = f"HTTP {response.status_code}"
                    break
                wait_seconds = RETRY_BACKOFF_BASE ** attempt
                print(
                    f"  [HTTP {response.status_code}] {context} "
                    f"{wait_seconds}秒待機して再試行します ({attempt}/{max_retries})"
                )
                time.sleep(wait_seconds)
                continue

            # 2xx もしくは 4xx（429以外のクライアントエラーは即エラー）
            response.raise_for_status()
            return response

        except requests.exceptions.Timeout:
            last_error = "タイムアウト"
            if exhausted:
                break
            wait_seconds = RETRY_BACKOFF_BASE ** attempt
            print(
                f"  [Timeout] {context} {wait_seconds}秒待機して再試行します "
                f"({attempt}/{max_retries})"
            )
            time.sleep(wait_seconds)
            continue

        except requests.exceptions.RequestException as e:
            # 429/5xxは上で処理済みなので、ここではその他のリクエスト例外を処理する
            # （ConnectionError, HTTPError などのサブクラスも含む）
            last_error = str(e)
            if exhausted:
                break
            wait_seconds = RETRY_BACKOFF_BASE ** attempt
            print(
                f"  [Error] {context} {wait_seconds}秒待機して再試行します "
                f"({attempt}/{max_retries}): {e}"
            )
            time.sleep(wait_seconds)
            continue

    # すべての試行が失敗した場合
    raise requests.exceptions.RequestException(
        f"{context} リクエストが{max_retries}回の試行後も成功しませんでした（最後の原因: {last_error}）"
    )


SEASON_GAME_KIND_IDS = {
    "2026": 249,     # 2026特別シーズン
    "2026-27": 2,    # 2026/27シーズン
}

FALLBACKS_FILE = Path(__file__).resolve().parent / "data" / "stat_fallbacks.csv"


def _load_stat_fallbacks():
    """外部CSVの補完値を (season, category, team, player_id, stat) で索引化する。"""
    fallbacks = {}
    if not FALLBACKS_FILE.exists():
        return fallbacks

    with FALLBACKS_FILE.open(newline="", encoding="utf-8-sig") as csv_file:
        for row_number, row in enumerate(csv.DictReader(csv_file), start=2):
            key = tuple(row[field].strip() for field in (
                "season", "category", "team", "player_id", "stat"
            ))
            if not all(key):
                raise ValueError(f"{FALLBACKS_FILE}:{row_number}: 必須項目が空です")
            if key in fallbacks:
                raise ValueError(f"{FALLBACKS_FILE}:{row_number}: 補完キーが重複しています: {key}")
            try:
                value = float(row["value"])
                if value.is_integer():
                    value = int(value)
            except (TypeError, ValueError):
                raise ValueError(f"{FALLBACKS_FILE}:{row_number}: value が数値ではありません")
            fallbacks[key] = {
                "value": value,
                "source_type": row["source_type"].strip(),
                "source_url": row["source_url"].strip(),
            }
    return fallbacks


def _fetch_player_roster(year, category, team):
    """選手スタッツページの選手フィルターから選手IDと名前を取得する。"""
    url = (
        f"https://www.jleague.jp/{category}/stats/player/"
        f"{year}/game/search-list/?club={team}"
    )
    time.sleep(REQUEST_INTERVAL)
    response = _request_with_retry(url, context=f"{team}の選手一覧")
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


def _fetch_team_stat_ranking(year, category, team, stat):
    """公式のチーム絞り込みランキングから選手別数値を取得する。"""
    url = (
        f"https://www.jleague.jp/{category}/stats/player/"
        f"{year}/{stat}/search-list/?club={team}"
    )
    time.sleep(REQUEST_INTERVAL)
    response = _request_with_retry(url, context=f"{team}の{stat}ランキング")
    html = response.text
    if r'\"rankingList\"' not in html:
        raise RuntimeError(f"チーム別ランキングが見つかりません (URL: {url})")

    # ペイロードはエスケープ済みJSON。順位表に載らない選手も、正常取得時は0と判定する。
    pattern = re.compile(
        r'\\"href\\":\\"/player/(\d+)/\\".*?'
        r'\\"points\\":([0-9]+(?:\.[0-9]+)?)',
        re.DOTALL,
    )
    values = {}
    for match in pattern.finditer(html):
        value = _parse_stat_number(match.group(2))
        if value is not None:
            values[match.group(1)] = value
    return values, url


PLAYER_HISTORY_STAT_KEYS = {
    "game": "出場試合数",
    "time": "出場時間",
    "score": "得点",
    "shoot": "シュート数",
    "yellow_count": "警告数",
    "red_count": "退場数",
}
GK_ONLY_STAT_KEYS = {
    "lost", "suffer_shoot", "suffer_shoot_on_target", "save_count", "save_rate",
    "save_count_per_game", "save_rate_in_pa", "save_rate_out_pa",
    "save_catch_rate_in_pa", "save_catch_rate_out_pa", "cross_catch_rate",
    "save_punch_rate_in_pa", "save_punch_rate_out_pa", "cross_punch_rate", "clean_sheet",
}
COMMON_PLAYER_STAT_KEYS = {
    "game", "time", "score", "shoot", "yellow_count", "red_count",
    "foul_count", "suffer_foul_count", "pass_count", "pass_rate", "pass_count_per_game",
    "long_pass_count", "long_pass_rate", "long_pass_count_per_game",
}


def _parse_stat_number(value):
    """詳細スタッツの表示値（単位・%付き）を数値にする。"""
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    if not match:
        return None
    number = float(match.group(0))
    return int(number) if number.is_integer() else number


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
    next_season = re.search(r'},\"\d{4}-\d+\":{', html[season_start:])
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


def _fetch_player_history_stats(player_id, season):
    """個人ページの試合履歴から、指定シーズンの基本スタッツを合算する。"""
    game_kind_id = SEASON_GAME_KIND_IDS[season]
    url = f"https://www.jleague.jp/player/{player_id}/?navicode=j1#stats"
    time.sleep(REQUEST_INTERVAL)
    response = _request_with_retry(
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


def collect_appearances(year, category, team, output_dir="output", selected_stats=None):
    """公式個人ページとチーム別ランキングから選手スタッツを集計する。"""
    if year not in SEASON_GAME_KIND_IDS:
        raise ValueError("出場試合数の集計は 2026 または 2026-27 に対応しています")

    players = _fetch_player_roster(year, category, team)
    fallbacks = _load_stat_fallbacks()
    print(f"選手一覧を取得しました: {len(players)}人")
    # チームで絞った公式ランキングを使うことで、移籍前後を分けたチーム在籍時の値を取る。
    # ポジションに存在する項目だけ取得し、同じチームの選手間ではランキングを共有する。
    selected_stats = set(selected_stats or STAT_NAME_MAP)
    applicable_stats = {
        stat for stat in STAT_NAME_MAP
        if stat in selected_stats
        if any(_is_stat_applicable(stat, p.get("position", "")) for p in players)
        and (category == "j1" or stat not in J1_ONLY_PHYSICAL_STAT_KEYS)
    }
    team_rankings = {}
    ranking_errors = {}
    for stat in STAT_NAME_MAP:
        if stat not in applicable_stats:
            continue
        try:
            team_rankings[stat] = _fetch_team_stat_ranking(year, category, team, stat)
        except (requests.exceptions.RequestException, RuntimeError) as e:
            ranking_errors[stat] = str(e)
            print(f"注意: {team} の {STAT_NAME_MAP[stat]}を取得できません: {e}")

    rows = []
    errors = []
    for index, player in enumerate(players, start=1):
        print(f"[{index}/{len(players)}] {player['player_name']} の出場履歴を取得中")
        player_url = f"https://www.jleague.jp/player/{player['player_id']}/?navicode=j1#stats"
        try:
            player_stats = _fetch_player_history_stats(player["player_id"], year)
            source_type = "選手個人ページ"
            source_url = player_url
            fetch_error = None
        except (requests.exceptions.RequestException, RuntimeError) as e:
            player_stats = {
                # 取得できなかった値を実績ゼロと区別する。ランキングや補完値で
                # 後から取得できた項目は、この None が実値に置き換わる。
                key: None
                for key in STAT_NAME_MAP
            }
            source_type = "未取得"
            source_url = ""
            fetch_error = str(e)

        player_fallbacks = {
            key[4]: value for key, value in fallbacks.items()
            if key[:4] == (year, category, team, player["player_id"])
        }
        # 成功した公式チーム別ランキングは、個人ページのシーズン合計より優先する。
        # ランキングに選手がいない場合は、順位外として0を記録する。
        for stat, (ranking, ranking_url) in team_rankings.items():
            if _is_stat_applicable(stat, player.get("position", "")):
                player_stats[stat] = ranking.get(player["player_id"], 0)
                if stat == "game":
                    source_type = "公式チーム別スタッツ"
                    source_url = ranking_url
        for stat, fallback in player_fallbacks.items():
            if stat not in STAT_NAME_MAP:
                continue
            if fallback["source_type"] == "公式チーム別スタッツ" or source_type == "未取得" or player_stats.get(stat) is None:
                player_stats[stat] = fallback["value"]
            if stat == "game" and (source_type == "未取得" or fallback["source_type"] == "公式チーム別スタッツ"):
                source_type = fallback["source_type"]
                source_url = fallback["source_url"]

        if fetch_error:
            required_stats = {
                stat for stat in STAT_NAME_MAP
                if stat in selected_stats
                if _is_stat_applicable(stat, player.get("position", ""))
                and (category == "j1" or stat not in J1_ONLY_PHYSICAL_STAT_KEYS)
            }
            available_stats = set(team_rankings) | set(player_fallbacks)
            if not required_stats.issubset(available_stats):
                errors.append((player["player_id"], player["player_name"], fetch_error))
        if ranking_errors:
            for stat, error in ranking_errors.items():
                if stat in selected_stats and _is_stat_applicable(stat, player.get("position", "")):
                    errors.append((
                        player["player_id"], player["player_name"],
                        f"{STAT_NAME_MAP[stat]}のチーム別ランキング取得失敗: {error}",
                    ))
        row = {
            "player_url": player_url,
            "player_name": player["player_name"],
            "team_name": {
                "shimizu": "清水エスパルス",
                "yokohamafc": "横浜FC",
            }.get(team, team),
            "source_type": source_type,
            "source_url": source_url,
            "_position": player.get("position", ""),
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
        _write_stat_failure_log(output_dir, year, category, team, error_rows)
        if error_rows:
            print(f"取得失敗ログ: {os.path.join(output_dir, f'stats_{team}_{year}_{category}_errors.csv')}")
    else:
        # 前回実行の失敗ログが残らないよう、既存ファイルがあれば空に更新する。
        _write_stat_failure_log(output_dir, year, category, team, [])
    return rows


def _is_stat_applicable(stat, position):
    """ポジション別スタッツの対象かを判定する。未知のポジションは対象扱い。"""
    if position == "GK":
        return stat in GK_ONLY_STAT_KEYS or stat in COMMON_PLAYER_STAT_KEYS
    if position in ("DF", "MF", "FW"):
        return stat not in GK_ONLY_STAT_KEYS
    return True

def _write_stat_failure_log(output_dir, year, category, team, failures):
    """取得失敗ログの出力処理をoutputモジュールへ委譲する。"""
    from output import write_stat_failure_log

    return write_stat_failure_log(output_dir, year, category, team, failures)
