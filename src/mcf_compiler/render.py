"""Sanitized Markdown, media, math, question, and page rendering."""

from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, quote, urlparse

import bleach
from latex2mathml.converter import convert as mathml
from markdown_it import MarkdownIt

from .model import Course, Lesson, Question

MARKDOWN = MarkdownIt("commonmark", {"html": True}).enable("table")
MEDIA_RE = re.compile(r"@\[(audio|video)\]\((\S+)(?:\s+(?:\"([^\"]*)\"|'([^']*)'))?\)")
IMAGE_RE = re.compile(r"(!\[[^\]]*\]\()([^\s)]+)([^)]*\))")
LINK_RE = re.compile(r"(?<!!)(\[[^\]]+\]\()([^\s)]+)([^)]*\))")
DISPLAY_MATH_RE = re.compile(r"\$\$([\s\S]*?)\$\$")
INLINE_MATH_RE = re.compile(r"(?<!\\)\$([^\n$]+)\$")

ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "pre",
    "img",
    "audio",
    "video",
    "source",
    "iframe",
    "figure",
    "figcaption",
    "small",
    "span",
    "div",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "math",
    "mrow",
    "mi",
    "mn",
    "mo",
    "mtext",
    "mspace",
    "ms",
    "mfrac",
    "msqrt",
    "mroot",
    "mstyle",
    "merror",
    "mpadded",
    "mphantom",
    "mfenced",
    "menclose",
    "msub",
    "msup",
    "msubsup",
    "munder",
    "mover",
    "munderover",
    "mmultiscripts",
    "mtable",
    "mtr",
    "mtd",
    "semantics",
    "annotation",
}
ALLOWED_ATTRIBUTES: dict[str, list[str]] = {
    "*": ["class", "data-mcf-question"],
    "img": ["src", "alt", "title", "loading"],
    "audio": ["src", "controls", "preload"],
    "video": ["src", "controls", "preload"],
    "iframe": [
        "src",
        "title",
        "loading",
        "referrerpolicy",
        "allow",
        "allowfullscreen",
    ],
    "a": ["href", "target", "rel", "class"],
    "code": ["class"],
    "span": ["class", "aria-hidden"],
    "div": ["class", "data-mcf-question"],
    "math": ["xmlns", "display", "alttext"],
    "annotation": ["encoding"],
    "mo": ["stretchy", "fence", "separator", "accent", "form"],
    "mspace": ["width", "height", "depth"],
    "mstyle": ["displaystyle", "scriptlevel", "mathvariant"],
    "mtable": ["columnalign", "rowspacing", "columnspacing"],
    "mtd": ["columnalign", "rowalign"],
}


def escape(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True).replace(
        "&#x27;", "&#39;"
    )


def safe_url(url: str) -> str:
    return url if re.match(r"^(?:https?:|mailto:|#|\.\./)", url, re.IGNORECASE) else "#"


def local_url(source: str, lesson: Lesson, course: Course) -> str:
    if re.match(r"^(?:https?:|youtube:)", source, re.IGNORECASE):
        return source
    absolute = ((course.root / lesson.source).parent / source).resolve()
    try:
        relative = absolute.relative_to(course.root.resolve()).as_posix()
    except ValueError:
        return "#"
    return f"../{relative}" if relative else "#"


def youtube_video_id(source: str) -> str | None:
    provider = re.fullmatch(r"youtube:([A-Za-z0-9_-]+)", source)
    if provider:
        return provider.group(1)
    try:
        parsed = urlparse(source)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        parts = [part for part in parsed.path.split("/") if part]
        if host == "youtu.be":
            return parts[0] if parts else None
        if host in {"youtube.com", "m.youtube.com", "youtube-nocookie.com"}:
            if parsed.path == "/watch":
                return parse_qs(parsed.query).get("v", [None])[0]
            if len(parts) >= 2 and parts[0] in {"embed", "shorts", "live"}:
                return parts[1] if re.fullmatch(r"[A-Za-z0-9_-]+", parts[1]) else None
    except ValueError:
        return None
    return None


def _math(source: str) -> str:
    expressions: list[tuple[str, bool]] = []
    token_prefix = "MCFMATHPLACEHOLDER"
    while token_prefix in source:
        token_prefix += "_"

    def protect(match: re.Match[str], display: bool) -> str:
        expressions.append((match.group(1).strip() if display else match.group(1), display))
        return f"{token_prefix}{len(expressions) - 1}END"

    protected = DISPLAY_MATH_RE.sub(lambda match: protect(match, True), source)
    protected = INLINE_MATH_RE.sub(lambda match: protect(match, False), protected)
    rendered = MARKDOWN.render(protected)

    def restore(match: re.Match[str]) -> str:
        expression, display = expressions[int(match.group(1))]
        try:
            converted = mathml(expression, display="block" if display else "inline")
            wrapped = f'<span class="katex">{converted}</span>'
            return f'<span class="katex-display">{wrapped}</span>' if display else wrapped
        except Exception as error:  # latex2mathml intentionally has varied parse exceptions
            return f'<span class="katex-error" title="{escape(error)}">{escape(expression)}</span>'

    return re.sub(rf"{re.escape(token_prefix)}(\d+)END", restore, rendered)


def rich(source: str, lesson: Lesson, course: Course) -> str:
    def media(match: re.Match[str]) -> str:
        kind, reference = match.group(1), match.group(2)
        label = match.group(3) or match.group(4) or ""
        video_id = youtube_video_id(reference) if kind == "video" else None
        if video_id:
            safe_id = escape(video_id)
            description = escape(label or "Remote video")
            link_label = escape(label or "video")
            return (
                '<div class="remote-media">'
                f'<iframe src="https://www.youtube-nocookie.com/embed/{safe_id}" '
                f'title="{description}" loading="lazy" '
                'referrerpolicy="strict-origin-when-cross-origin" '
                'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; '
                'picture-in-picture; web-share" allowfullscreen></iframe>'
                '<a class="remote-video-fallback" '
                f'href="https://www.youtube.com/watch?v={safe_id}" '
                'target="_blank" rel="noopener noreferrer">'
                f'<img src="https://i.ytimg.com/vi/{safe_id}/hqdefault.jpg" alt="">'
                f"<span>Open {link_label} on YouTube</span></a>"
                "<small>Remote media — internet required. YouTube embeds require an HTTP server; "
                "direct-file readers can use the link above.</small></div>"
            )
        url = escape(safe_url(local_url(reference, lesson, course)))
        caption = f"<figcaption>{escape(label)}</figcaption>" if label else ""
        notice = (
            "<small>Remote media — internet required</small>"
            if re.match(r"^https?:", reference, re.IGNORECASE)
            else ""
        )
        return (
            f'<figure><{kind} controls preload="metadata" src="{url}"></{kind}>'
            f"{caption}{notice}</figure>"
        )

    authored = MEDIA_RE.sub(media, source)
    authored = IMAGE_RE.sub(
        lambda match: (
            f"{match.group(1)}{safe_url(local_url(match.group(2), lesson, course))}{match.group(3)}"
        ),
        authored,
    )

    def link(match: re.Match[str]) -> str:
        reference = match.group(2)
        url = (
            reference
            if re.match(r"^(?:https?:|mailto:|#)", reference, re.IGNORECASE)
            else safe_url(local_url(reference, lesson, course))
        )
        return f"{match.group(1)}{url}{match.group(3)}"

    authored = LINK_RE.sub(link, authored)
    return bleach.clean(
        _math(authored),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols={"http", "https", "mailto"},
        strip=True,
        strip_comments=True,
    )


def question_html(question: Question, lesson: Lesson, course: Course, *, assessment: bool) -> str:
    name = f"{lesson.id}-{question.id}"
    if question.type in {"multiple_choice", "multiple_select"}:
        input_type = "checkbox" if question.type == "multiple_select" else "radio"
        control = "\n".join(
            f'<label class="option"><input type="{input_type}" name="{escape(name)}" '
            f'value="{escape(option.id)}"> <span>{rich(option.text, lesson, course)}</span></label>'
            for option in question.options or []
        )
    elif question.type == "true_false":
        control = "\n".join(
            f'<label class="option"><input type="radio" name="{escape(name)}" value="{value}"> '
            f"{'True' if value == 'true' else 'False'}</label>"
            for value in ("true", "false")
        )
    elif question.type == "essay":
        control = '<textarea rows="7" aria-label="Essay response"></textarea>'
    else:
        input_type = "number" if question.type == "numeric" else "text"
        step = ' step="any"' if question.type == "numeric" else ""
        control = f'<input class="text-response" type="{input_type}"{step} aria-label="Response">'
    hint_button = '<button class="hint-button" type="button">Hint</button>' if question.hint else ""
    check_button = (
        ""
        if assessment
        else (
            '<button class="check-button" type="button">'
            f"{'Check completion' if question.type == 'essay' else 'Check answer'}</button>"
        )
    )
    hint = (
        f'<div class="hint hidden">{rich(question.hint, lesson, course)}</div>'
        if question.hint
        else ""
    )
    explanation = (
        f'<div class="explanation hidden">{rich(question.explanation, lesson, course)}</div>'
        if question.explanation
        else ""
    )
    return f"""<section class="question" data-id="{escape(question.id)}"
  data-type="{escape(question.type)}">
  <div class="prompt">{rich(question.prompt, lesson, course)}</div>
  <div class="responses">{control}</div>
  <div class="question-actions">{hint_button}{check_button}</div>
  {hint}
  <div class="feedback" aria-live="polite"></div>
  {explanation}
</section>"""


def lesson_body(lesson: Lesson, course: Course) -> str:
    sections: list[str] = []
    for activity in lesson.activities:
        body = rich(activity.content, lesson, course)
        for question in activity.questions:
            body = body.replace(
                f'<div data-mcf-question="{question.id}"></div>',
                question_html(question, lesson, course, assessment=activity.type == "assessment"),
            )
        type_label = (
            ""
            if activity.type == "notes"
            else (f'<span class="eyebrow">{escape(activity.type)}</span>')
        )
        notes_button = (
            '<button class="notes-complete" type="button">Mark notes complete</button>'
            if activity.type == "notes"
            else ""
        )
        assessment_button = (
            '<button class="assessment-submit" type="button">Submit assessment</button>'
            '<p class="assessment-result" aria-live="polite"></p>'
            if activity.type == "assessment"
            else ""
        )
        sections.append(
            f"""<section class="activity" data-activity="{escape(activity.id)}"
  data-type="{escape(activity.type)}">
  <header>{type_label}<h2>{escape(activity.title or activity.id)}</h2></header>
  <div class="questions">{body}</div>
  {notes_button}
  {assessment_button}
</section>"""
        )
    return "\n".join(sections)


def page(
    title: str,
    language: str,
    body: str,
    css: str = "styles.css",
    script: str | None = None,
    extra_css: str | None = None,
) -> str:
    return f"""<!doctype html>
<html lang="{escape(language)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{escape(title)}</title>
  <link rel="stylesheet" href="{escape(css)}">
  {f'<link rel="stylesheet" href="{escape(extra_css)}">' if extra_css else ""}
</head>
<body>
{body}
{f'<script src="{escape(script)}"></script>' if script else ""}
</body>
</html>
"""


def encoded_lesson_id(lesson_id: str) -> str:
    return quote(lesson_id, safe="")
