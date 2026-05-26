import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    for _ in range(2):
        next_value = html.unescape(value)
        if next_value == value:
            break
        value = next_value
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n\s*\n\s*", "\n\n", value)
    return value.strip()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if self._skip_depth:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n\n")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in {"p", "br", "div", "section", "article", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag in {
            "p",
            "li",
            "div",
            "section",
            "article",
            "tr",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        }:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            cleaned = re.sub(r"\s+", " ", data).strip()
            if cleaned:
                if (
                    self.parts
                    and self.parts[-1]
                    and not self.parts[-1].endswith((" ", "\n", "- "))
                    and not cleaned.startswith((",", ".", ";", ":", ")", "]"))
                ):
                    self.parts.append(" ")
                self.parts.append(cleaned)

    def text(self) -> str:
        return _normalize_text("".join(self.parts))


@dataclass
class ScrapedJob:
    title: str
    company: str
    url: str
    location: str | None
    raw_jd: str
    source: str | None
    source_job_id: str | None
    posted_at: datetime | None
    employment_type: str | None
    workplace: str | None
    salary_text: str | None
    scraped_json: dict


def _strip_html(value: str | None) -> str:
    parser = _TextExtractor()
    decoded = value or ""
    for _ in range(2):
        next_value = html.unescape(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    parser.feed(decoded)
    return parser.text()


def _meta(html_text: str, *names: str) -> str | None:
    for name in names:
        patterns = [
            rf'<meta[^>]+(?:name|property)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\']{re.escape(name)}["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_text, re.IGNORECASE | re.DOTALL)
            if match:
                return _normalize_text(match.group(1))
    return None


def _page_title(html_text: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    return _normalize_text(match.group(1)) if match else None


def _json_ld_objects(html_text: str) -> list[dict]:
    objects: list[dict] = []
    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
        re.IGNORECASE | re.DOTALL,
    )
    for script in scripts:
        try:
            loaded = json.loads(html.unescape(script).strip())
        except json.JSONDecodeError:
            continue
        stack = loaded if isinstance(loaded, list) else [loaded]
        while stack:
            item = stack.pop(0)
            if not isinstance(item, dict):
                continue
            objects.append(item)
            graph = item.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)
    return objects


def _find_job_posting_jsonld(html_text: str) -> dict | None:
    for item in _json_ld_objects(html_text):
        item_type = item.get("@type")
        types = item_type if isinstance(item_type, list) else [item_type]
        if any(str(t).lower() == "jobposting" for t in types):
            return item
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _location_from_jsonld(job_json: dict) -> str | None:
    locations = job_json.get("jobLocation")
    if not locations:
        return None
    if isinstance(locations, dict):
        locations = [locations]
    parts: list[str] = []
    for item in locations if isinstance(locations, list) else []:
        address = item.get("address") if isinstance(item, dict) else None
        if not isinstance(address, dict):
            continue
        location_parts = [
            address.get("addressLocality"),
            address.get("addressRegion"),
            address.get("addressCountry"),
        ]
        location = ", ".join(str(p) for p in location_parts if p)
        if location:
            parts.append(location)
    return "; ".join(parts) if parts else None


def _salary_from_jsonld(job_json: dict) -> str | None:
    salary = job_json.get("baseSalary")
    if not isinstance(salary, dict):
        return None
    currency = salary.get("currency")
    value = salary.get("value")
    if isinstance(value, dict):
        min_value = value.get("minValue")
        max_value = value.get("maxValue")
        unit = value.get("unitText")
        if min_value and max_value:
            return " ".join(str(p) for p in (currency, f"{min_value}-{max_value}", unit) if p)
        if value.get("value"):
            return " ".join(str(p) for p in (currency, value.get("value"), unit) if p)
    return None
