import requests
import csv
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
try:
    import pandas as pd
except ImportError:
    pd = None
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
import re
import argparse
import os
import sys
from pathlib import Path

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

def get_team_list(year, category):
    """指定された年とカテゴリのチームスラッグ一覧を取得する"""
    url = f"https://www.jleague.jp/stats/{category}/player/{year}/all/score/"
    try:
        response = _get_session().get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        # "クラブを選択してください" を含む select を特定してから option を取得する
        teams = []
        target_select = None
        for sel in soup.find_all("select"):
            if sel.find("option", string=lambda s: s and "クラブを選択してください" in s):
                target_select = sel
                break

        if not target_select:
            # チーム候補を動的に取得できなかった場合、呼び出し側が区別できるよう
            # 警告を出した上で空リストを返す
            print(
                f"警告: チーム一覧のHTML構造が見つかりませんでした (URL: {url})。"
                "サイトの構造変更が考えられます。"
            )
            return []

        options = target_select.find_all("option")
        found_club_label = False
        for opt in options:
            val = opt.get("value", "")
            text = opt.text.strip()
            if "クラブを選択してください" in text:
                found_club_label = True
                continue
            if found_club_label and val != "all" and val != "":
                if "シーズンを選択してください" in text or "項目を選択してください" in text:
                    break
                teams.append(val)
        return teams
    except requests.exceptions.RequestException as e:
        # ネットワークエラーとHTTPエラーを区別して報告する
        print(f"チーム一覧の取得に失敗しました（ネットワークまたはHTTPエラー）: {e}")
        return []
    except Exception as e:
        print(f"チーム一覧の解析中に予期しないエラーが発生しました: {e}")
        return []

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
        year = prompt_input("取得したいシーズン（4桁）", "2025")
        year = _normalize_year(year)
        if _is_valid_year(year):
            break
        print("  4桁の半角数字（例: 2025）で入力してください。")

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


def fetch_stat(stat_type, year, category, team, strict=False):
    url = f"https://www.jleague.jp/stats/{category}/player/{year}/{team}/{stat_type}/"

    # サーバー負荷軽減のため、固定待機を入れる
    time.sleep(REQUEST_INTERVAL)

    context = f"{team}の{stat_type}"
    response = _request_with_retry(url, context=context)
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    
    ranking_list = soup.find("ul", class_="ranking_list")
    if not ranking_list:
        msg = f"{team}の{stat_type}ランキング取得失敗 (URL: {url})"

        if strict:
            raise RuntimeError(msg)
        else:
            print("WARNING:", msg)
            return None
        
    items = ranking_list.find_all("li")
    
    for li in items:
        if "ranking_header" in li.get("class", []) or li.find("p", class_="rank_title"):
            continue

        name_tag = li.find("p", class_="name")
        link_tag = li.find("a")
        team_tag = li.find("p", class_="team")
        value_tag = (
            li.select_one("div[class^='ranking_stats_'] p")
            or li.select_one("div.ranking_stats p")
        )

        if not (name_tag and value_tag):
            continue

        name = name_tag.text.strip()
        # 名前が空、またはヘッダーの残骸をスキップ
        if not name or name == "選手名":
            continue

        team_name = team_tag.text.strip() if team_tag else ""
        raw_value = value_tag.text.strip()
        clean_value = raw_value.replace(",", "")
        value_match = re.search(r'(\d+\.?\d*)', clean_value)
        value = value_match.group(1) if value_match else "0"
        
        player_url = "https://www.jleague.jp" + link_tag["href"] if link_tag else ""

        rows.append({
            "player_url": player_url,
            "player_name": name,
            "team_name": team_name,
            stat_type: value
        })
    
    # チーム名補完
    if rows:
        valid_team_names = [r["team_name"] for r in rows if r["team_name"]]
        if valid_team_names:
            most_common_team = max(set(valid_team_names), key=valid_team_names.count)
            for r in rows:
                if not r["team_name"]:
                    r["team_name"] = most_common_team
    
    return pd.DataFrame(rows)


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
    for player_id, name in re.findall(
        r'\\"value\\":\\"(\d+)\\",\\"label\\":\\"([^"\\]+)\\"', block
    ):
        if player_id not in seen:
            players.append({"player_id": player_id, "player_name": name})
            seen.add(player_id)
    if not players:
        raise RuntimeError(f"選手一覧を解析できません (URL: {url})")
    return players


PLAYER_HISTORY_STAT_KEYS = {
    "game": "出場試合数",
    "time": "出場時間",
    "score": "得点",
    "shoot": "シュート数",
    "yellow_count": "警告数",
    "red_count": "退場数",
}


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
    return stats


def collect_appearances(year, category, team, output_dir="output"):
    """公式サイトの選手履歴から、チームの選手別基本スタッツを集計する。"""
    if year not in SEASON_GAME_KIND_IDS:
        raise ValueError("出場試合数の集計は 2026 または 2026-27 に対応しています")

    players = _fetch_player_roster(year, category, team)
    fallbacks = _load_stat_fallbacks()
    print(f"選手一覧を取得しました: {len(players)}人")
    rows = []
    errors = []
    for index, player in enumerate(players, start=1):
        print(f"[{index}/{len(players)}] {player['player_name']} の出場履歴を取得中")
        player_url = f"https://www.jleague.jp/player/{player['player_id']}/?navicode=j1#stats"
        try:
            player_stats = _fetch_player_history_stats(player["player_id"], year)
            source_type = "選手個人ページ"
            source_url = player_url
        except (requests.exceptions.RequestException, RuntimeError) as e:
            fallback_key = (year, category, team, player["player_id"], "game")
            fallback = fallbacks.get(fallback_key)
            errors.append((player["player_id"], player["player_name"], str(e)))
            if fallback is None:
                player_stats = {key: 0 for key in PLAYER_HISTORY_STAT_KEYS}
                source_type = "未取得"
                source_url = ""
            else:
                player_stats["game"] = fallback["value"]
                source_type = fallback["source_type"]
                source_url = fallback["source_url"]
        row = {
            "player_url": player_url,
            "player_name": player["player_name"],
            "team_name": "清水エスパルス" if team == "shimizu" else team,
            "source_type": source_type,
            "source_url": source_url,
        }
        row.update(player_stats)
        rows.append(row)

    if errors:
        print(f"注意: {len(errors)}人は履歴を確認できず、取得失敗スタッツは0にします:")
        for player_id, name, error in errors:
            print(f"  {name} ({player_id}): {error}")
        error_rows = []
        for player_id, name, error in errors:
            player_url = f"https://www.jleague.jp/player/{player_id}/?navicode=j1#stats"
            for stat_key, stat_label in PLAYER_HISTORY_STAT_KEYS.items():
                if stat_key == "game" and (year, category, team, player_id, "game") in fallbacks:
                    continue
                error_rows.append((team, name, player_url, stat_label, error))
        _write_stat_failure_log(output_dir, year, category, team, error_rows)
        if error_rows:
            print(f"取得失敗ログ: {os.path.join(output_dir, f'stats_{team}_{year}_{category}_errors.csv')}")
    return rows

def _normalize_player_url(df):
    if "player_url" in df.columns:
        df["player_url"] = df["player_url"].fillna("").astype(str)
    return df


def _dedupe_players(df):
    """選手を一意化する。

    優先順位:
      1. player_url があるものを採用する
      2. player_url がない場合は 名前 + チーム名 で一意化する

    旧実装は「URLあり」と「URLなし」の行を別々に drop_duplicates してから
    結合していたため、同一選手（例: game ページにはURLあり、score ページにはURLなし）
    が2行残っていた。フェーズごとのURLの有無が食い違うことは実際に 일어나るため、
    ここでは URL 優先でまとめたうえで、名前+チームが一致する行は同一選手として扱う。
    """
    if df.empty:
        return df.reset_index(drop=True)

    df = _normalize_player_url(df.copy())

    # チーム名が欠損している場合は、結合キーが壊れないように空文字へ寄せる
    if "team_name" in df.columns:
        df["team_name"] = df["team_name"].fillna("").astype(str)
    if "player_name" in df.columns:
        df["player_name"] = df["player_name"].fillna("").astype(str)

    # 1) URL が一意に決まる行を確定（同名選手でもURLが違えば別人とみなす）
    with_url = df[df["player_url"] != ""].drop_duplicates(subset=["player_url"], keep="first")

    # 2) URL がない行は、名前+チームで一意化する
    without_url = df[df["player_url"] == ""]
    if not without_url.empty:
        without_url = without_url.drop_duplicates(subset=["player_name", "team_name"], keep="first")

    if with_url.empty:
        return without_url.reset_index(drop=True)
    if without_url.empty:
        return with_url.reset_index(drop=True)

    # 3) 名前+チームが一致する「URLなし」行は、既存の「URLあり」行と同一選手とみなす
    known_keys = set(zip(with_url["player_name"], with_url["team_name"]))
    absorbed_mask = without_url.apply(
        lambda r: (r["player_name"], r["team_name"]) in known_keys, axis=1
    )
    absorbed = without_url[absorbed_mask]
    if not absorbed.empty:
        print(
            f"  注意: {len(absorbed)}件の.URLなし行が同一選手のURLあり行と重複したため、"
            "URLあり行に統合しました。"
        )

    kept_without_url = without_url[~absorbed_mask]
    merged = pd.concat([with_url, kept_without_url], ignore_index=True)
    return merged.reset_index(drop=True)

def _merge_stat_by_key(final_df, df_stat, stat_col):
    """player_url優先で結合。URLなしは名前+チームで結合する。

    該当する行が見つからない場合は 0 で埋める。元の行を取りこぼさない。
    旧実装は空DataFrameに `df[col] = []` を代入しており、意味のない列を作っていた。
    """
    final_df = _normalize_player_url(final_df.copy())
    df_stat = _normalize_player_url(df_stat.copy())

    final_with_url = final_df[final_df["player_url"] != ""].copy()
    final_without_url = final_df[final_df["player_url"] == ""].copy()

    stat_with_url = (
        df_stat[df_stat["player_url"] != ""][["player_url", stat_col]]
        .drop_duplicates(subset=["player_url"])
    )
    stat_without_url = (
        df_stat[df_stat["player_url"] == ""][["player_name", "team_name", stat_col]]
        .drop_duplicates(subset=["player_name", "team_name"])
    )

    parts = []
    if not final_with_url.empty:
        merged_with = pd.merge(final_with_url, stat_with_url, on="player_url", how="left")
        merged_with[stat_col] = merged_with[stat_col].fillna(0)
        parts.append(merged_with)

    if not final_without_url.empty:
        merged_without = pd.merge(
            final_without_url, stat_without_url, on=["player_name", "team_name"], how="left"
        )
        merged_without[stat_col] = merged_without[stat_col].fillna(0)
        parts.append(merged_without)

    if not parts:
        # 元データが行がない場合は、列のみを持つ空DataFrameを返す
        empty = final_df.copy()
        empty[stat_col] = pd.Series(dtype="object")
        return empty

    return pd.concat(parts, ignore_index=True)


def _write_stat_failure_log(output_dir, year, category, team, failures):
    """取得に失敗したスタッツを、通常のCSVとは別のログCSVに記録する。"""
    if not failures:
        return
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"stats_{team}_{year}_{category}_errors.csv")
    with open(filepath, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["チーム", "選手名", "選手URL", "項目", "理由"])
        writer.writerows(failures)

def collect_team_stats(year, category, team, output_dir="output", strict=False):
    stat_types = list(STAT_NAME_MAP.keys())
    print(f"--- Target: {year} {category} {team} ---")

    # --- Step 1: 選手マスタ（ベース）の作成 ---
    # 'game'（出場試合数）と 'score'（得点）を取得して、全選手リストを作成する
    print("Creating player master list...")
    base_stats = ["game", "score"]
    master_df = None
    base_stats_cache = {}

    for st in base_stats:
        df = fetch_stat(st, year, category, team, strict=strict)
        if df is None or df.empty:
            url = f"https://www.jleague.jp/stats/{category}/player/{year}/{team}/{st}/"
            raise RuntimeError(f"{team}の{st}ランキング取得失敗 (URL: {url})")
        base_stats_cache[st] = df

        # 必要な基本カラムだけ抽出
        df_base = df[["player_url", "player_name", "team_name"]].copy()

        if master_df is None:
            master_df = df_base
        else:
            # 選手リストを統合する。重複排除は最後にまとめて行う。
            master_df = pd.concat([master_df, df_base], ignore_index=True)

    if master_df is None or master_df.empty:
        raise RuntimeError(f"{team}の選手マスタ作成に失敗しました (URL: https://www.jleague.jp/stats/{category}/player/{year}/{team}/game/)")

    # 重複排除（マスタ作成）
    # player_url優先で一意化し、URLが無い場合は名前+チームで一意化する
    master_df = _dedupe_players(master_df)

    print(f"Master list created: {len(master_df)} players found.")

    # --- Step 2: 全スタッツを左結合していく ---
    final_df = master_df.copy()
    failed_stats = []
    failure_log_rows = []

    for i, st in enumerate(stat_types):
        message = f"[{i+1}/{len(stat_types)}] データ取得中: {st}..."
        # 前の行が長い場合に残らないよう、行をクリアしてから表示
        sys.stdout.write("\r" + " " * 100 + "\r")
        sys.stdout.write(message)
        sys.stdout.flush()

        if st in base_stats_cache:
            df = base_stats_cache[st]
        else:
            try:
                df = fetch_stat(st, year, category, team, strict=strict)
            except requests.exceptions.RequestException as e:
                # ネットワークエラーは当該項目だけを失敗として扱い、全体は継続する
                if strict:
                    raise
                sys.stdout.write("\r" + " " * 100 + "\r")
                print(f"  [取得失敗] {st}: {e}")
                df = None
                failed_stats.append(st)

        if df is None or df.empty:
            url = f"https://www.jleague.jp/stats/{category}/player/{year}/{team}/{st}/"
            if strict:
                raise RuntimeError(f"{team}の{st}ランキング取得失敗 (URL: {url})")
            else:
                # 非strictは0埋めで継続
                if st not in failed_stats:
                    sys.stdout.write("\r" + " " * 100 + "\r")
                    print(f"  [取得失敗] {st} のランキングが空です (URL: {url})")
                    failed_stats.append(st)
                failure_reason = f"ランキング取得失敗 (URL: {url})"
                failure_log_rows.extend(
                    (team, row["player_name"], row["player_url"], st, failure_reason)
                    for _, row in master_df.iterrows()
                )
                final_df[st] = 0
                continue

        # マージ用にカラムを絞る（URLはマスタにあるので不要、名前とチーム名で結合）
        # ただし、結合用キー以外はスタッツ値だけにする
        cols_to_use = ["player_url", "player_name", "team_name", st]
        df_to_merge = _dedupe_players(df[cols_to_use])

        # 左結合 (Left Join)
        # これにより、マスタにいない「謎の行」が増えるのを防ぐ
        try:
            final_df = _merge_stat_by_key(final_df, df_to_merge, st)
        except Exception as e:
            sys.stdout.write("\r" + " " * 100 + "\r")
            print(f"  [警告] {st} の結合に失敗しました: {e}")
            final_df[st] = 0
            failed_stats.append(st)
            failure_log_rows.extend(
                (team, row["player_name"], row["player_url"], st, f"結合失敗: {e}")
                for _, row in master_df.iterrows()
            )

    if failed_stats:
        sys.stdout.write("\r" + " " * 100 + "\r")
        print(
            f"  注意: {len(failed_stats)}/{len(stat_types)} 項目を取得できませんでした。"
            "該当列は 0 で埋めています: " + ", ".join(failed_stats)
        )
        if not strict:
            print(
                "        実際の値が 0 の選手と区別できません。"
                "--strict を付けると取得失敗時に中断します。"
            )
        _write_stat_failure_log(output_dir, year, category, team, failure_log_rows)
        if failure_log_rows:
            print(f"  取得失敗ログ: {os.path.join(output_dir, f'stats_{team}_{year}_{category}_errors.csv')}")

    print(f"\n全スタッツの取得が完了しました: {team}")
    return final_df

def main():
    parser = argparse.ArgumentParser(description="J.League Player Stats Collector")
    parser.add_argument("--year", default="2025", help="取得したいシーズン（例: 2025 / 2026-27）")
    parser.add_argument("--category", default="j1", choices=["j1", "j2", "j3"], help="カテゴリ（j1 / j2 / j3）")
    parser.add_argument("--team", default="shimizu", help="チームスラッグ（例: shimizu / kashima / all）")
    parser.add_argument("--output", default="output", help="保存先フォルダ（例: output）")
    parser.add_argument("--interactive", action="store_true", help="対話式ウィザードで実行する")
    parser.add_argument("--list-teams", action="store_true", help="チーム一覧を表示して終了する")
    parser.add_argument("--strict", action="store_true", help="厳格モード（ランキングが見つからない場合は例外で中断）")
    parser.add_argument(
        "--appearances-only", "--player-history-stats",
        action="store_true",
        help="選手個人ページから取得できる基本スタッツを集計する（2026 / 2026-27、J1）",
    )
    
    args = parser.parse_args()

    # CLI引数の --year も正規化する（全角数字→半角変換 + 妥当性検証）
    args.year = _normalize_year(args.year)
    if args.appearances_only:
        if args.year not in SEASON_GAME_KIND_IDS:
            parser.error("--appearances-only は --year 2026 または 2026-27 を指定してください")
        if args.category != "j1":
            parser.error("--appearances-only は現在J1に対応しています")
        if args.team == "all":
            parser.error("--appearances-only は現在チームを1つ指定してください")
    elif not _is_valid_year(args.year):
        parser.error(f"--year は4桁の半角数字で指定してください（入力値: {args.year!r}）")
    elif BeautifulSoup is None or pd is None:
        parser.error("通常の全スタッツ取得には依存パッケージが必要です。pip install -r requirements.txt を実行してください")

    # 引数なし、または対話式指定ならウィザードを起動
    if args.interactive or len(sys.argv) == 1:
        year, category, team, output = interactive_wizard()
        args.year = year
        args.category = category
        args.team = team
        args.output = output

    if args.list_teams:
        teams = get_team_list(args.year, args.category)
        if teams:
            print(f"チーム一覧（{args.year} {args.category}）:")
            print(", ".join(teams))
        else:
            print("チーム一覧の取得に失敗しました。")
        return

    if args.appearances_only:
        final_df = collect_appearances(args.year, args.category, args.team, args.output)
        os.makedirs(args.output, exist_ok=True)
        filename = f"stats_{args.team}_{args.year}_{args.category}.csv"
        filepath = os.path.join(args.output, filename)
        columns = [
            ("player_url", "選手URL"),
            ("player_name", "選手名"),
            ("team_name", "チーム名"),
            *((stat, STAT_NAME_MAP[stat]) for stat in ("game", "time", "score", "shoot", "yellow_count", "red_count")),
            ("source_type", "出場試合数の取得方法"),
            ("source_url", "出場試合数の出典URL"),
        ]
        with open(filepath, "w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([label for _, label in columns])
            writer.writerows([[row[key] for key, _ in columns] for row in final_df])
        print(f"\nSUCCESS: Saved to {filepath}")
        print(f"Total players: {len(final_df)}")
        return
    
    if args.team == "all":
        print("all は全チーム取得のため、10〜15分程度かかる場合があります。")
        if not prompt_yes_no("実行しますか？", default="n"):
            print("キャンセルしました。")
            return
        teams = get_team_list(args.year, args.category)
        if not teams:
            print("チーム一覧が取得できなかったため、処理を中止します。")
            return
        print(f"Found {len(teams)} teams for {args.year} {args.category}: {', '.join(teams)}")

        all_teams_df = []
        failed_teams = []
        for i, t in enumerate(teams):
            print(f"\n[Team {i+1}/{len(teams)}] Processing {t}...")
            # 1チームの失敗で全体が止まると、それまでに取得したデータが
            # すべて破棄されてしまうため、チーム単位でエラーを隔離する
            try:
                team_df = collect_team_stats(
                    args.year, args.category, t, args.output, strict=args.strict
                )
            except Exception as e:
                print(f"  [チーム失敗] {t}: {e}")
                failed_teams.append(t)
                continue

            if team_df is not None and not team_df.empty:
                all_teams_df.append(team_df)

        if failed_teams:
            print(
                f"\n警告: {len(failed_teams)}/{len(teams)} チームで失敗しました: "
                + ", ".join(failed_teams)
            )

        if not all_teams_df:
            print("No data collected for any team.")
            return

        final_df = pd.concat(all_teams_df, ignore_index=True)
        # 最後に全体で重複排除（念のため）
        final_df = _dedupe_players(final_df)
    else:
        final_df = collect_team_stats(args.year, args.category, args.team, args.output, strict=args.strict)

    if final_df is None or final_df.empty:
        print("No data collected.")
        return

    # 数値列は数値型に統一する。
    # 旧実装は DataFrame 全体を fillna("0") していたため、player_url の欠損が
    # 文字列 "0" になって出力されていた。ここでは統計列だけを処理する。
    for st in STAT_NAME_MAP.keys():
        if st in final_df.columns:
            final_df[st] = pd.to_numeric(final_df[st], errors="coerce").fillna(0)

    # 文字列列の欠損は空文字にする（URLに "0" が入るのを防ぐ）
    for col in ("player_url", "player_name", "team_name"):
        if col in final_df.columns:
            final_df[col] = final_df[col].fillna("").astype(str)

    rename_map = {
        "player_url": "選手URL",
        "player_name": "選手名",
        "team_name": "チーム名"
    }
    
    original_cols = final_df.columns.tolist()
    
    for st, label in STAT_NAME_MAP.items():
        if st in original_cols:
            rename_map[st] = label
    
    ordered_cols = ["player_url", "player_name", "team_name"] + [st for st in STAT_NAME_MAP.keys() if st in original_cols]
    final_df = final_df[ordered_cols]
    final_df = final_df.rename(columns=rename_map)

    if not os.path.exists(args.output):
        os.makedirs(args.output)
        
    filename = f"stats_{args.team}_{args.year}_{args.category}.csv"
    filepath = os.path.join(args.output, filename)
    final_df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"\nSUCCESS: Saved to {filepath}")
    print(f"Total players: {len(final_df)}")

if __name__ == "__main__":
    main()
