"""スタッツ項目の定義（コード↔日本語名）、ポジション判定、シーズン定数。

サイト取得やCSV出力から独立した、純粋な「定義とルール」だけを置く。
"""

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

# 個人ページの試合履歴から合算できる基本スタッツ（表示名付き）。
PLAYER_HISTORY_STAT_KEYS = {
    "game": "出場試合数",
    "time": "出場時間",
    "score": "得点",
    "shoot": "シュート数",
    "yellow_count": "警告数",
    "red_count": "退場数",
}

# GKだけが対象となる項目。
GK_ONLY_STAT_KEYS = {
    "lost", "suffer_shoot", "suffer_shoot_on_target", "save_count", "save_rate",
    "save_count_per_game", "save_rate_in_pa", "save_rate_out_pa",
    "save_catch_rate_in_pa", "save_catch_rate_out_pa", "cross_catch_rate",
    "save_punch_rate_in_pa", "save_punch_rate_out_pa", "cross_punch_rate", "clean_sheet",
}

# 全ポジション共通で対象となる項目。
COMMON_PLAYER_STAT_KEYS = {
    "game", "time", "score", "shoot", "yellow_count", "red_count",
    "foul_count", "suffer_foul_count", "pass_count", "pass_rate", "pass_count_per_game",
    "long_pass_count", "long_pass_rate", "long_pass_count_per_game",
}

# シーズンごとの gameKindId（個人ページの詳細スタッツのシーズンキーに使う）。
SEASON_GAME_KIND_IDS = {
    **{str(year): 2 for year in range(2018, 2026)},  # 通常シーズン
    "2026": 249,     # 2026特別シーズン
    "2026-27": 2,    # 2026/27シーズン
}

# 現行登録選手との照合に使うシーズン。リーグのシーズン形式変更時に更新する。
CURRENT_PLAYER_LIST_SEASON = "2026-27"


def stat_keys_for_category(category):
    """カテゴリで取得できるスタッツ項目の一覧を返す（J2/J3はフィジカル系を除く）。"""
    if category in ("j2", "j3"):
        return [key for key in STAT_NAME_MAP if key not in J1_ONLY_PHYSICAL_STAT_KEYS]
    return list(STAT_NAME_MAP)


def is_stat_applicable(stat, position):
    """ポジション別スタッツの対象かを判定する。未知のポジションは対象扱い。"""
    if position == "GK":
        return stat in GK_ONLY_STAT_KEYS or stat in COMMON_PLAYER_STAT_KEYS
    if position in ("DF", "MF", "FW"):
        return stat not in GK_ONLY_STAT_KEYS
    return True
