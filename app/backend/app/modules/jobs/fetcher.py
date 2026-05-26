import httpx
from urllib.parse import urlparse

DEFAULT_JOB_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
    )
}

PLAIN_JOB_REQUEST_HEADERS = {
    "User-Agent": "python-httpx",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _request_headers_for_url(url: str) -> dict[str, str]:
    host = urlparse(url).netloc.removeprefix("www.")
    if host == "bmwgroup.jobs":
        return PLAIN_JOB_REQUEST_HEADERS
    return DEFAULT_JOB_REQUEST_HEADERS


def _fallback_headers_for_url(url: str, current_headers: dict[str, str]) -> dict[str, str] | None:
    if current_headers == PLAIN_JOB_REQUEST_HEADERS:
        return None
    return PLAIN_JOB_REQUEST_HEADERS


async def _fetch_job_page(client: httpx.AsyncClient, url: str) -> tuple[httpx.Response, str]:
    headers = _request_headers_for_url(url)
    try:
        return await client.get(url, headers=headers), (
            "plain" if headers == PLAIN_JOB_REQUEST_HEADERS else "browser"
        )
    except httpx.TimeoutException:
        fallback_headers = _fallback_headers_for_url(url, headers)
        if not fallback_headers:
            raise
        return await client.get(url, headers=fallback_headers), "plain_retry_after_timeout"


async def _fetch_greenhouse_board_name(client: httpx.AsyncClient, board: str) -> str | None:
    from app.modules.jobs.extractor import _normalize_text

    try:
        response = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{board}")
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    name = data.get("name")
    return _normalize_text(str(name)) if name else None
