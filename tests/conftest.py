"""pytest 共通設定。

ここには「全テストで使うお膳立て」を置く。個別のテストは tests/test_*.py に書く。
`load_fixture` と `make_fake_response` は各テストから import して使う。
"""

import os
import sys

import pytest
import requests

# リポジトリ直下の scraper.py / output.py / main.py を import できるようにする。
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import scraper  # noqa: E402  (sys.path を通してから import する)

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load_fixture(name):
    """tests/fixtures/ 以下のファイルを文字列として読み込む。"""
    with open(os.path.join(FIXTURES_DIR, name), encoding="utf-8") as handle:
        return handle.read()


def make_fake_response(text, status=200, headers=None):
    """requests.Response の代わりに使う、最小限のダミー応答を返す。

    実際にネットワークへ出ないよう、サイトのレスポンスをこれに差し替える。
    """

    class FakeResponse:
        def __init__(self):
            self.text = text
            self.status_code = status
            self.headers = headers or {}
            self.url = "https://example.com"

        def raise_for_status(self):
            # requests と同じく、4xx/5xx のときは例外を投げる。
            if self.status_code >= 400:
                error = requests.exceptions.HTTPError(f"HTTP {self.status_code}")
                error.response = self
                raise error

    return FakeResponse()


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """テスト中に実際へ待機しないよう、scraper の time.sleep を無効化する。

    autouse=True なので、すべてのテストで自動的に適用される。
    """
    monkeypatch.setattr(scraper.time, "sleep", lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def _reset_scraper_caches():
    """テスト同士が影響し合わないよう、モジュール内キャッシュを毎回リセットする。"""
    scraper._team_name_maps.clear()
    scraper._current_player_ids = None
    scraper._current_player_list_error = None
    scraper._current_player_list_loaded = False
    yield
    scraper._team_name_maps.clear()
    scraper._current_player_ids = None
    scraper._current_player_list_error = None
    scraper._current_player_list_loaded = False
