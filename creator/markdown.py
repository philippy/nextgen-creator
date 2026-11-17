import re

from django.utils.html import escape
from django.utils.safestring import mark_safe

HEADING = re.compile(r"^(#{1,3})\s+(.+)")
BULLET = re.compile(r"^[-*]\s+(.+)")
NUMBER = re.compile(r"^\d+\.\s+(.+)")
BOLD = re.compile(r"\*\*([^*]+)\*\*")


def inline(text):
    return BOLD.sub(r"<strong>\1</strong>", escape(text))


def render_markdown(source):
    output = []
    block = None
    for line in source.splitlines():
        line = line.strip()
        heading = HEADING.fullmatch(line)
        bullet = BULLET.fullmatch(line)
        number = NUMBER.fullmatch(line)
        kind = "ul" if bullet else "ol" if number else "p" if line and not heading else None

        if block != kind:
            if block:
                output.append(f"</{block}>")
            if kind:
                output.append(f"<{kind}>")
        elif block == "p":
            output.append("<br>")
        block = kind

        if heading:
            level = len(heading[1]) + 1
            output.append(f"<h{level}>{inline(heading[2])}</h{level}>")
        elif bullet or number:
            output.append(f"<li>{inline((bullet or number)[1])}</li>")
        elif line:
            output.append(inline(line))
    if block:
        output.append(f"</{block}>")
    return mark_safe("".join(output))
