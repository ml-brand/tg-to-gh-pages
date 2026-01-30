from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from typing import List, Optional, Set
from urllib.parse import urlparse

SAFE_SCHEMES: Set[str] = {"http", "https", "mailto", "tg", "tel"}


def _is_safe_href(href: Optional[str]) -> bool:
    if not href:
        return False
    href = href.strip()
    if href.startswith("//"):
        return False
    if href.startswith(("/", "#", "./", "../")):
        return True
    parsed = urlparse(href)
    if parsed.scheme.lower() in SAFE_SCHEMES:
        return True
    return False


def sanitize_links(html_text: str) -> str:
    """Ensure links use safe schemes and contain rel=noopener/noreferrer/nofollow."""

    class _Sanitizer(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=False)
            self.out: List[str] = []

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, Optional[str]]]
        ) -> None:
            self.out.append(self._build_tag(tag, attrs, False))

        def handle_startendtag(
            self, tag: str, attrs: list[tuple[str, Optional[str]]]
        ) -> None:
            self.out.append(self._build_tag(tag, attrs, True))

        def _build_tag(
            self, tag: str, attrs: list[tuple[str, Optional[str]]], self_closing: bool
        ) -> str:
            attrs_out = attrs
            if tag.lower() == "a":
                attrs_dict = {k: v for k, v in attrs}
                href = attrs_dict.get("href")
                if not _is_safe_href(href):
                    attrs_dict.pop("href", None)
                rel_raw = attrs_dict.get("rel", "") or ""
                rel_set = {
                    token
                    for token in rel_raw.replace(",", " ").split()
                    if token.strip()
                }
                rel_set.update({"noopener", "noreferrer", "nofollow"})
                attrs_dict["rel"] = " ".join(sorted(rel_set))
                attrs_out = list(attrs_dict.items())

            buf = [f"<{tag}"]
            for k, v in attrs_out:
                if v is None:
                    buf.append(f" {k}")
                else:
                    buf.append(f' {k}="{escape(v, quote=True)}"')
            buf.append(" />" if self_closing else ">")
            return "".join(buf)

        def handle_endtag(self, tag: str) -> None:
            self.out.append(f"</{tag}>")

        def handle_data(self, data: str) -> None:
            self.out.append(data)

        def handle_entityref(self, name: str) -> None:
            self.out.append(f"&{name};")

        def handle_charref(self, name: str) -> None:
            self.out.append(f"&#{name};")

        def get_html(self) -> str:
            return "".join(self.out)

    parser = _Sanitizer()
    parser.feed(html_text or "")
    return parser.get_html()
