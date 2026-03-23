import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import argparse
import os
import sys

# HTTP request timeout (connect, read) in seconds
REQUEST_TIMEOUT = (5, 20)

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
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
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
    except Exception as e:
        print(f"Error fetching team list: {e}")
        return []

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
        if re.fullmatch(r"\d{4}", year):
            break
        print("  4桁の数字（例: 2025）で入力してください。")

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

def fetch_stat(stat_type, year, category, team):
    url = f"https://www.jleague.jp/stats/{category}/player/{year}/{team}/{stat_type}/"
    
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"  {team}の{stat_type}を取得する際にエラーが発生しました: {e}")
        print("ヒント：入力内容（チーム名・年度など）を確認してください")
        raise

    soup = BeautifulSoup(response.text, "html.parser")
    rows = []
    
    ranking_list = soup.find("ul", class_="ranking_list")
    if not ranking_list:
        return pd.DataFrame(columns=["player_url", "player_name", "team_name", stat_type])
        
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

def collect_team_stats(year, category, team, output_dir="output"):
    stat_types = list(STAT_NAME_MAP.keys())
    print(f"--- Target: {year} {category} {team} ---")
    
    # --- Step 1: 選手マスタ（ベース）の作成 ---
    # 'game'（出場試合数）と 'score'（得点）を取得して、全選手リストを作成する
    print("Creating player master list...")
    base_stats = ["game", "score"]
    master_df = None
    
    for st in base_stats:
        df = fetch_stat(st, year, category, team)
        if df.empty:
            continue
        
        # 必要な基本カラムだけ抽出
        df_base = df[["player_url", "player_name", "team_name"]].copy()
        
        if master_df is None:
            master_df = df_base
        else:
            # マージして選手リストを統合（URLなし選手も名前とチーム名で統合）
            # URLが空の場合は、空でない方を優先して採用するロジックが必要だが、
            # 単純に結合してから重複排除する
            master_df = pd.concat([master_df, df_base], ignore_index=True)
    
    if master_df is None or master_df.empty:
        print("Could not create player master list. Aborting.")
        return pd.DataFrame()

    # 重複排除（マスタ作成）
    # 名前とチーム名でユニークにする。URLがある行を優先して残したいので、URLでソートする
    master_df = master_df.sort_values("player_url", ascending=False)
    master_df = master_df.drop_duplicates(subset=["player_name", "team_name"])
    
    print(f"Master list created: {len(master_df)} players found.")

    # --- Step 2: 全スタッツを左結合していく ---
    final_df = master_df.copy()
    
    for i, st in enumerate(stat_types):
        message = f"[{i+1}/{len(stat_types)}] データ取得中: {st}..."
        # 前の行が長い場合に残らないよう、行をクリアしてから表示
        sys.stdout.write("\r" + " " * 100 + "\r")
        sys.stdout.write(message)
        sys.stdout.flush()
        df = fetch_stat(st, year, category, team)
        
        if df.empty:
            final_df[st] = "0"
            continue
        
        # マージ用にカラムを絞る（URLはマスタにあるので不要、名前とチーム名で結合）
        # ただし、結合用キー以外はスタッツ値だけにする
        cols_to_use = ["player_name", "team_name", st]
        df_to_merge = df[cols_to_use].drop_duplicates(subset=["player_name", "team_name"])
        
        # 左結合 (Left Join)
        # これにより、マスタにいない「謎の行」が増えるのを防ぐ
        try:
            final_df = pd.merge(final_df, df_to_merge, on=["player_name", "team_name"], how="left")
            
            # 結合できなかった（NaN）場所は "0" で埋める
            final_df[st] = final_df[st].fillna("0")
            
        except Exception as e:
            print(f"\n  Warning: Could not merge {st}: {e}")
            final_df[st] = "0"
        
        time.sleep(0.3)
    
    print(f"\n全スタッツの取得が完了しました: {team}")
    return final_df

def main():
    parser = argparse.ArgumentParser(description="J.League Player Stats Collector")
    parser.add_argument("--year", default="2025", help="取得したいシーズン（例: 2025）")
    parser.add_argument("--category", default="j1", choices=["j1", "j2", "j3"], help="カテゴリ（j1 / j2 / j3）")
    parser.add_argument("--team", default="shimizu", help="チームスラッグ（例: shimizu / kashima / all）")
    parser.add_argument("--output", default="output", help="保存先フォルダ（例: output）")
    parser.add_argument("--interactive", action="store_true", help="対話式ウィザードで実行する")
    parser.add_argument("--list-teams", action="store_true", help="チーム一覧を表示して終了する")
    
    args = parser.parse_args()

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
    
    if args.team == "all":
        print("all は全チーム取得のため、10〜15分程度かかる場合があります。")
        if not prompt_yes_no("実行しますか？", default="n"):
            print("キャンセルしました。")
            return
        teams = get_team_list(args.year, args.category)
        print(f"Found {len(teams)} teams for {args.year} {args.category}: {', '.join(teams)}")
        
        all_teams_df = []
        for i, t in enumerate(teams):
            print(f"\n[Team {i+1}/{len(teams)}] Processing {t}...")
            team_df = collect_team_stats(args.year, args.category, t, args.output)
            if team_df is not None and not team_df.empty:
                all_teams_df.append(team_df)
        
        if not all_teams_df:
            print("No data collected for any team.")
            return
            
        final_df = pd.concat(all_teams_df, ignore_index=True)
        # 最後に全体で重複排除（念のため）
        final_df = final_df.drop_duplicates(subset=["player_name", "team_name"])
    else:
        final_df = collect_team_stats(args.year, args.category, args.team, args.output)

    if final_df is None or final_df.empty:
        print("No data collected.")
        return

    final_df = final_df.fillna("0")
    
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
