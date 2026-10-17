"""クラブスラッグ → 公式チーム名の取得。

チーム一覧は実行内でキャッシュする（同じページを何度も取りに行かないため）。
"""

import json
import re

import requests

from http_client import REQUEST_TIMEOUT, get_session

_team_name_maps = {}


def _team_name_map(year, category):
    """クラブスラッグから公式チーム名へのマッピングを返す（実行内キャッシュ）。

    現行サイトは select 要素ではなく、Next.js の RSC ペイロードに
    id="club" の選択肢（value: スラッグ, label: 正式名）を JSON として
    埋め込んでいる。取得・解析に失敗した場合は空のマッピングを返す。
    """
    key = (year, category)
    if key in _team_name_maps:
        return _team_name_maps[key]
    name_map = {}
    url = f"https://www.jleague.jp/{category}/stats/player/{year}/score/search-list/"
    try:
        response = get_session().get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.text.replace(r'\"', '"')
        club_options = re.search(
            r'"id":"club".*?"id":"club-all".*?"options":(\[.*?\])',
            payload,
            re.DOTALL,
        )
        if club_options:
            options = json.loads(club_options.group(1))
            for option in options:
                slug = option.get("value", "")
                if slug and slug != "all":
                    name_map[slug] = option.get("label") or slug
        else:
            print(
                f"警告: クラブ一覧データが見つかりません (URL: {url})。"
                "サイトの構造変更が考えられます。"
            )
    except requests.exceptions.RequestException as e:
        # ネットワークエラーとHTTPエラーを区別して報告する
        print(f"チーム一覧の取得に失敗しました（ネットワークまたはHTTPエラー）: {e}")
    except Exception as e:
        print(f"チーム一覧の解析中に予期しないエラーが発生しました: {e}")
    _team_name_maps[key] = name_map
    return name_map


def get_team_list(year, category):
    """現行の公式スタッツページからクラブ選択肢のスラッグ一覧を取得する。"""
    return list(_team_name_map(year, category))


def get_team_name(year, category, slug):
    """クラブスラッグに対応する公式チーム名を返す。不明な場合はスラッグを返す。"""
    return _team_name_map(year, category).get(slug, slug)
