"""HTTPリトライ処理のテスト。

実際にネットワークへ出ないよう、requests.Session をダミーに差し替え、
「429 / 5xx / タイムアウト / 切断 / 4xx」で期待どおり動くかを確かめる。
"""

import datetime

import pytest
import requests

import scraper
from conftest import make_fake_response


class FakeSession:
    """get() が呼ばれるたびに、あらかじめ並べた結果を1つ返すダミー。"""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _install_session(monkeypatch, outcomes):
    session = FakeSession(outcomes)
    monkeypatch.setattr(scraper, "_get_session", lambda: session)
    return session


def test_returns_response_on_success(monkeypatch):
    _install_session(monkeypatch, [make_fake_response("ok")])
    response = scraper._request_with_retry("https://example.com")
    assert response.text == "ok"


def test_honours_retry_after_header_on_429(monkeypatch):
    slept = []
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds, *a, **k: slept.append(seconds))
    _install_session(
        monkeypatch,
        [
            make_fake_response("", status=429, headers={"Retry-After": "3"}),
            make_fake_response("ok"),
        ],
    )

    response = scraper._request_with_retry("https://example.com")

    assert response.text == "ok"
    assert 3 in slept  # Retry-After の秒数だけ待機した


def test_retries_on_server_error_then_succeeds(monkeypatch):
    session = _install_session(
        monkeypatch, [make_fake_response("", status=503), make_fake_response("ok")]
    )
    assert scraper._request_with_retry("https://example.com").text == "ok"
    assert session.calls == 2


def test_gives_up_after_repeated_server_errors(monkeypatch):
    _install_session(monkeypatch, [make_fake_response("", status=503)] * 3)
    with pytest.raises(requests.exceptions.RequestException):
        scraper._request_with_retry("https://example.com", max_retries=3)


def test_gives_up_after_repeated_timeouts(monkeypatch):
    _install_session(monkeypatch, [requests.exceptions.Timeout("遅い")] * 3)
    with pytest.raises(requests.exceptions.RequestException):
        scraper._request_with_retry("https://example.com", max_retries=3)


def test_reconnects_and_retries_on_connection_error(monkeypatch):
    session = _install_session(
        monkeypatch,
        [requests.exceptions.ConnectionError("切断"), make_fake_response("ok")],
    )
    assert scraper._request_with_retry("https://example.com").text == "ok"
    assert session.calls == 2


def test_does_not_retry_client_error(monkeypatch):
    # 404 などはリトライしても直らないので、1回で即エラーにする。
    session = _install_session(monkeypatch, [make_fake_response("not found", status=404)])
    with pytest.raises(requests.exceptions.RequestException):
        scraper._request_with_retry("https://example.com")
    assert session.calls == 1


# ---------------------------------------------------------------------------
# Retry-After ヘッダの解釈
# ---------------------------------------------------------------------------
def test_parse_retry_after_seconds():
    assert scraper._parse_retry_after({"Retry-After": "120"}) == 120


def test_parse_retry_after_missing_or_invalid():
    assert scraper._parse_retry_after({}) is None
    assert scraper._parse_retry_after({"Retry-After": "いつになるかわからない"}) is None


def test_parse_retry_after_http_date(monkeypatch):
    class FrozenDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.datetime(2026, 10, 21, 7, 24, 0, tzinfo=datetime.timezone.utc)

    monkeypatch.setattr(scraper, "datetime", FrozenDateTime)

    # 現在時刻 07:24:00 から 07:28:00 までは 240 秒
    assert scraper._parse_retry_after({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}) == 240
    # すでに過ぎていれば 0（すぐ再試行してよい）
    assert scraper._parse_retry_after({"Retry-After": "Wed, 21 Oct 2026 07:20:00 GMT"}) == 0
