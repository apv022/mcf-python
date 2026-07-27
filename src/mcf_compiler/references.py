"""Rich-content reference extraction."""

from markdown_it import MarkdownIt

MARKDOWN = MarkdownIt("commonmark")


def markdown_references(source: str) -> list[str]:
    """Return links and images from live CommonMark nodes."""
    references: list[str] = []
    for token in MARKDOWN.parse(source):
        for child in token.children or []:
            if child.type == "link_open":
                href = child.attrGet("href")
                if isinstance(href, str):
                    references.append(href)
            elif child.type == "image":
                src = child.attrGet("src")
                if isinstance(src, str):
                    references.append(src)
    return references
