import csv
import os


def write_inactive_player_csv(output_dir, year, category, team, players):
    """現行J1/J2/J3選手一覧にない過去選手をCSVに保存する。"""
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(
        output_dir, f"players_not_current_{team}_{year}_{category}.csv"
    )
    with open(filepath, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow([
            "対象シーズン", "対象カテゴリ", "対象チーム", "選手ID", "選手名",
            "ポジション", "選手URL", "現行J1/J2/J3一覧",
        ])
        for player in players:
            player_id = player["player_id"]
            writer.writerow([
                year, category, player.get("_team_slug", team), player_id, player["player_name"],
                player.get("position", ""),
                f"https://www.jleague.jp/player/{player_id}/?navicode=j1#stats",
                "掲載なし",
            ])
    return filepath


def write_auto_inactive_player_csv(output_dir, year, category, team, players):
    """通常取得で検出した現行Jリーグ一覧にない選手をCSVに保存する。"""
    inactive = [player for player in players if player.get("_absent_from_current_list")]
    return write_inactive_player_csv(output_dir, year, category, team, inactive)


def write_stat_failure_log(output_dir, year, category, team, failures):
    """取得に失敗したスタッツを通常のCSVとは別に記録する。"""
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"stats_{team}_{year}_{category}_errors.csv")
    if not failures and not os.path.exists(filepath):
        return
    with open(filepath, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["チーム", "選手名", "選手URL", "項目", "理由"])
        writer.writerows(failures)


def write_stats_csv(
    rows, output_dir, team, year, category, selected_stats,
    stat_names, physical_stat_keys, is_stat_applicable,
):
    """選手スタッツをExcelで開けるUTF-8 BOM付きCSVに保存する。"""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"stats_{team}_{year}_{category}.csv"
    filepath = os.path.join(output_dir, filename)
    columns = [
        ("player_url", "選手URL"),
        ("player_name", "選手名"),
        ("team_name", "チーム名"),
        *((stat, stat_names[stat]) for stat in selected_stats),
    ]

    def csv_value(row, key):
        value = row.get(key)
        if key in stat_names and value is None:
            # ポジションの対象外項目は空欄、対象項目の未取得値はハイフン。
            if (
                is_stat_applicable(key, row.get("_position", ""))
                and not (category in ("j2", "j3") and key in physical_stat_keys)
            ):
                return "-"
        return value

    with open(filepath, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow([label for _, label in columns])
        writer.writerows([
            [csv_value(row, key) for key, _ in columns]
            for row in rows
        ])
    return filepath
