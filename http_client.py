"""Jリーグ公式サイトへのHTTPアクセス（リトライ・レート制限対応）。

ここには通信だけを置く。HTMLの解析やCSV出力は別モジュールが担当する。
"""

import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

# HTTP request timeout (connect, read) in seconds
REQUEST_TIMEOUT = (5, 20)

# リトライ回数
MAX_RETRIES = 3

# リトライ間の基本待機秒数（指数バックオフ）
RETRY_BACKOFF_BASE = 2

# サーバー負荷軽減のため、リクエスト間の固定待機秒数
REQUEST_INTERVAL = 0.5

# 同一セッションでリクエストを実行するための Session
_session = None


def get_session():
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


def _reset_session():
    """切断後の接続プールを破棄し、次の試行で新しい接続を使う。"""
    global _session
    if _session is not None:
        _session.close()
        _session = None


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


def request_with_retry(url, context="", max_retries=MAX_RETRIES, timeout=REQUEST_TIMEOUT):
    """GETリクエストをリトライ付きで実行する。成功時はレスポンスを返す。

    リトライ対象:
      - 429 Too Many Requests（Retry-Afterヘッダがあれば従う）
      - 5xx サーバーエラー（指数バックオフ）
      - タイムアウト / 接続エラー（指数バックオフ）

    429以外の4xxクライアントエラー（404など）はリトライしても成功しないため、即エラーにする。

    旧実装には「全試行がタイムアウトだと response が未代入のまま参照され
    UnboundLocalError になる」「429のレスポンスをデータとして解析する」といった
    不具合があった。ループが確実に response を返すよう構造を改めた。
    """
    last_error = None

    for attempt in range(1, max_retries + 1):
        exhausted = attempt >= max_retries
        try:
            # 前回の通信が途中で切れた場合は、ここで新しい Session を取得する。
            response = get_session().get(url, timeout=timeout)

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

        except (
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ConnectionError,
        ) as e:
            # Response ended prematurely などの途中切断では、壊れた keep-alive
            # 接続をプールから外してから短い待機で再試行する。
            last_error = str(e)
            _reset_session()
            if exhausted:
                break
            wait_seconds = min(attempt, 2)
            print(
                f"  [接続切断] {context} {wait_seconds}秒待機して新しい接続で再試行します "
                f"({attempt}/{max_retries}): {e}"
            )
            time.sleep(wait_seconds)
            continue

        except requests.exceptions.HTTPError as e:
            # 429/5xxは上で処理済みなので、ここに来るのは4xxクライアントエラーのみ
            # （404など）。リトライしても成功しないため、即エラーとする。
            status_code = e.response.status_code if e.response is not None else "不明"
            raise requests.exceptions.RequestException(
                f"{context} リクエストがHTTP {status_code}で失敗しました"
                f"（クライアントエラーのためリトライしません）: {e}"
            ) from e

        except requests.exceptions.RequestException as e:
            # 429/5xx/4xxは上で処理済みなので、ここではその他のリクエスト例外を処理する
            # （ConnectionErrorなどのサブクラスも含む）
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
