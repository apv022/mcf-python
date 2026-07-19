from __future__ import annotations

from mcf_compiler.parser import parse_course
from mcf_compiler.render import lesson_body, rich, youtube_video_id

from .conftest import NODE_REPOSITORY


def _context():  # type: ignore[no-untyped-def]
    course = parse_course(NODE_REPOSITORY / "examples/showcase")
    return course, course.chapters[0].lessons[0]


def test_markdown_tables_local_and_remote_media_render() -> None:
    course, lesson = _context()
    rendered = rich(lesson.activities[0].content, lesson, course)
    for element in ("<h2>", "<strong>", "<table>", "<pre>", "<img", "<audio", "<video", "<iframe"):
        assert element in rendered
    assert '<img src="../assets/images/path.svg"' in rendered
    assert "Remote media" in rendered


def test_inline_display_derivatives_and_malformed_math_are_graceful() -> None:
    course = parse_course(NODE_REPOSITORY / "examples/calculus-i")
    lesson = course.chapters[2].lessons[0]
    rendered = rich(
        "$f'(x)=2x$\n\n$$f'(x)=\\lim_{h\\to0}\\frac{f(x+h)-f(x)}{h}$$",
        lesson,
        course,
    )
    assert 'class="katex"' in rendered
    assert 'class="katex-display"' in rendered
    assert "<math" in rendered
    malformed = rich("$\\notacommand{$", lesson, course)
    assert "notacommand" in malformed or "katex-error" in malformed


def test_internal_math_placeholder_collision_is_avoided() -> None:
    course, lesson = _context()
    literal = "MCFMATHPLACEHOLDER0END"
    rendered = rich(f"{literal} and $x$", lesson, course)
    assert literal in rendered
    assert rendered.count('class="katex"') == 1


def test_authored_html_is_sanitized() -> None:
    course, lesson = _context()
    rendered = rich(
        '<script>alert(1)</script><img src="javascript:alert(1)" '
        'onerror="alert(2)"><a href="data:text/html,bad">bad</a>',
        lesson,
        course,
    )
    lowered = rendered.lower()
    assert "<script" not in lowered
    assert "onerror" not in lowered
    assert "javascript:" not in lowered
    assert "data:text" not in lowered


def test_question_controls_are_accessible_and_do_not_expose_answers() -> None:
    course = parse_course(NODE_REPOSITORY / "examples/showcase")
    lesson = course.chapters[0].lessons[1]
    rendered = lesson_body(lesson, course)
    assert 'data-type="multiple_choice"' in rendered
    assert 'aria-live="polite"' in rendered
    assert 'aria-label="Essay response"' in rendered
    assert "data-answer" not in rendered
    assert "<script" not in rendered


def test_youtube_reference_variants() -> None:
    expected = "Dw_tGRblTXk"
    assert youtube_video_id(f"youtube:{expected}") == expected
    assert youtube_video_id(f"https://www.youtube.com/watch?v={expected}") == expected
    assert youtube_video_id(f"https://youtu.be/{expected}") == expected
    assert youtube_video_id(f"https://www.youtube.com/embed/{expected}") == expected
    assert youtube_video_id("https://example.com/video") is None
