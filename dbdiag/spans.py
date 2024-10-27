import bisect
import textwrap
import dataclasses
import enum
from typing import NamedTuple, Optional, TypeAlias
from . import parser
from .constants import *

# Used to assign spans to a row, and keep track of how many rows need to exist
# so that no span ever overlaps with another.
# Each span acquire()s at its start, release()s at its end, and
# max_token() gives the maximum number ever allocated at once.
class TokenBucket(object):
    def __init__(self):
        self._tokens = []
        self._max_token = -1

    def acquire(self) -> int:
        if self._tokens:
            token = self._tokens[0]
            self._tokens.pop(0)
        else:
            self._max_token += 1
            token = self._max_token
        return token

    def release(self, token : int) -> None:
        bisect.insort(self._tokens, token)

    def max_token(self) -> int:
        return self._max_token

@dataclasses.dataclass
class Span(object):
    actor : str
    start : int
    end : int
    height : int
    text : tuple[Optional[str], Optional[str]]
    eventpoint : Optional[int]
    x1 : Optional[UnitsCh] = None
    x2 : Optional[UnitsCh] = None
    event_x : Optional[UnitsCh] = None
    y : Optional[UnitsPx] = None

@dataclasses.dataclass
class SpanStart(object):
    op : str
    start : int
    height : int
    eventpoint : Optional[int] = None

class SpanInfo(NamedTuple):
    spans : list[Span]
    actors : list[str]
    depths : dict[str, TokenBucket]

def operations_to_spans(operations : list[parser.Operation]) -> SpanInfo:
    inflight : dict[str, SpanStart] = {}
    actors_names : list[str] = []
    actor_depth : dict[str, TokenBucket] = {}
    spans : list[Span] = []

    for idx, group in enumerate(operations):
        for op in group:
            if op.actor not in actors_names:
                actors_names.append(op.actor)
            if op.actor not in actor_depth:
                actor_depth[op.actor] = TokenBucket()

            actorkey = (op.actor, op.key)
            if op.op == 'EVENT':
                inflight[actorkey].eventpoint = idx
            elif actorkey not in inflight:
                token = actor_depth[op.actor].acquire()
                inflight[actorkey] = SpanStart(op.op, idx, token)
            else:
                start = inflight[actorkey]
                del inflight[actorkey]
                x = idx
                spans.append(Span(op.actor, start.start, x, start.height, (start.op, op.op), start.eventpoint))
                actor_depth[op.actor].release(start.height)

    depths = {k: v.max_token()+1 for k,v in actor_depth.items()}
    return SpanInfo(spans, actors_names, depths)

#### Data Model

class Dimension(object):
    def __init__(self, dist, unit):
        self._dist = dist
        self._unit = unit

    def __str__(self):
        if EMBED and self._unit == 'ch':
            return f'{self._dist * CH_WIDTH_IN_PX}px'
        else:
            return f'{self._dist}{self._unit}'

    @staticmethod
    def from_ch(ch : UnitsCh) -> 'Dimension':
        return Dimension(ch, 'ch')

    @staticmethod
    def from_px(px : UnitsPx) -> 'Dimension':
        return Dimension(px, 'px')

class Actor(NamedTuple):
    name : str
    x : int
    y : int
    width : int
    height : int

class Chart(NamedTuple):
    actors : list[Actor]
    spans : list[Span]
    width : Dimension
    height : Dimension
    max_actor_width : UnitsCh

def span_width(span : Span) -> int:
    (left, right) = span.text
    chars = len(left or "") + len(right or "")
    both = left and right
    ret = chars + (INNER_INNER_BUFFER if both else 0) + INNER_BUFFER * 2
    return ret

def spans_to_chart(spaninfo : SpanInfo) -> Chart:
    actors = []

    max_actor_width = max(len(actor) for actor in spaninfo.actors)

    base_heights = {}
    current_height = 0
    for actor in spaninfo.actors:
        actor_x = OUTER_BUFFER # + max_actor_width/2
        actor_y = PX_SPAN_VERTICAL + current_height * PX_SPAN_VERTICAL - PX_LINE_TEXT_SEPARATION - PX_CHAR_HEIGHT
        actor_width = max_actor_width
        actor_height = (spaninfo.depths[actor]) * PX_SPAN_VERTICAL
        actors.append(Actor(actor, actor_x, actor_y, actor_width, actor_height))

        base_heights[actor] = current_height
        current_height += spaninfo.depths[actor]

    for span in spaninfo.spans:
        span.x1 = span.start * OUTER_BUFFER
        span.x2 = span.x1 + span_width(span)
        if span.eventpoint:
            span.event_x = span.eventpoint * OUTER_BUFFER

        span.y = (base_heights[span.actor] + span.height) * PX_SPAN_VERTICAL

    made_change = True
    while made_change:
        made_change = False
        for span in spaninfo.spans:
            beforeevent = afterevent = None
            for other in spaninfo.spans:
                if other.start < span.start and span.x1 < other.x1 + OUTER_BUFFER:
                    made_change = True
                    span.x1 = other.x1 + OUTER_BUFFER
                    span.x2 = max(span.x2, span.x1 + span_width(span))
                if other.end < span.start and span.x1 < other.x2 + OUTER_BUFFER:
                    made_change = True
                    span.x1 = other.x2 + OUTER_BUFFER
                    span.x2 = max(span.x2, span.x1 + span_width(span))
                if other.end < span.end and span.x2 < other.x2 + OUTER_BUFFER:
                    made_change = True
                    span.x2 = other.x2 + OUTER_BUFFER
                if span.eventpoint:
                    if other.start == span.eventpoint-1:
                        beforeevent = other.x1
                    if other.end == span.eventpoint-1:
                        beforeevent = other.x2
                    if other.eventpoint == span.eventpoint-1:
                        beforeevent = other.event_x
                    if other.start == span.eventpoint+1:
                        afterevent = other.x1
                    if other.end == span.eventpoint+1:
                        afterevent = other.x2
                    if other.eventpoint == span.eventpoint+1:
                        afterevent = other.event_x
            if span.eventpoint:
                if beforeevent is None or afterevent is None:
                    made_change = True
                elif span.event_x != (beforeevent + afterevent)/2:
                    made_change = True
                    span.event_x = (beforeevent + afterevent)/2

    OFFSET_X = OUTER_BUFFER + max_actor_width + CH_ACTOR_SPAN_SEPARATION
    OFFSET_Y = PX_SPAN_VERTICAL

    for span in spaninfo.spans:
        # adjust to make room for actor panel
        span.x1 += OFFSET_X
        span.x2 += OFFSET_X
        span.y += OFFSET_Y
        if span.event_x:
            span.event_x += OFFSET_X

    chart_width = max(span.x2 for span in spaninfo.spans) + OUTER_BUFFER
    chart_height = current_height * PX_SPAN_VERTICAL + OFFSET_Y + PX_CHAR_HEIGHT
    return Chart(actors, spaninfo.spans, Dimension.from_ch(chart_width), Dimension.from_px(chart_height), max_actor_width)

#### Renderer

def svg_header(width : Dimension, height : Dimension) -> str:
    header = f'''<svg version="1.1" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'''
    header += textwrap.dedent("""
    <defs>
        <style type="text/css">
            @media (prefers-color-scheme: dark) {
                text {
                    fill: #eceff4;
                }
                line {
                    stroke: #eceff4;
                }
            }""")
    if EMBED:
        header += textwrap.dedent("""
            text {
                font-size: 12px;
                font-family: monospace;
            }""")
    header += textwrap.dedent("""
            </style>
        </defs>""")
    return header

def svg_footer() -> str:
    return '</svg>'

class SVG(object):
    class XAlign(enum.StrEnum):
        START = "start"
        MIDDLE = "middle"
        END = "end"

    class YAlign(enum.StrEnum):
        TOP = "text-top"
        MIDDLE = "middle"
        BOTTOM = "baseline"

    def __init__(self, width : Dimension, height : Dimension):
        super()
        self._width = width
        self._height = height
        self._svg = []
        self._svg.append(svg_header(self._width, self._height))
        self._rendered = None
    
    def line(self, x1 : Dimension, y1 : Dimension, x2 : Dimension, y2 : Dimension):
        self._svg.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="black" />'
        )
    
    def text(self, x : Dimension, y : Dimension, xalign : XAlign, yalign : YAlign, text : str, font = None):
        font_family = f' font-family="{font}"' if font else ''
        self._svg.append(
            f'<text x="{x}" y="{y}" text-anchor="{xalign}" alignment-baseline="{yalign}"{font_family}>{text}</text>'
        )

    def circle(self, x : Dimension, y : Dimension, r : Dimension):
        self._svg.append(
            f'<circle cx="{x}" cy="{y}" r="{r}" />'
        )

    def render(self):
        if self._rendered:
            return self._rendered
        self._svg.append(svg_footer())
        self._rendered = '\n'.join(self._svg)
        return self._rendered

def svg_actor(svg : SVG, actor : Actor) -> str:
    lines = []
    text_x = Dimension.from_ch(actor.x)
    text_y = Dimension.from_px(actor.y + actor.height / 2)
    svg.text(text_x, text_y, SVG.XAlign.MIDDLE, SVG.YAlign.MIDDLE, actor.name, font="monospace")
    line_x = Dimension.from_ch(actor.x + actor.width + CH_ACTOR_SPAN_SEPARATION / 2)
    top_y = Dimension.from_px(actor.y + PX_ACTORBAR_SEPARATION)
    bottom_y = Dimension.from_px(actor.y + actor.height - PX_ACTORBAR_SEPARATION)
    svg.line(line_x, top_y, line_x, bottom_y)
    if DEBUG:
        svg.line('0%', top_y, '100%', top_y)
        svg.line('0%', bottom_y, '100%', bottom_y)
    return '\n'.join(lines)

def svg_span(svg : SVG, span : Span) -> str:
    svg.line(Dimension.from_ch(span.x1), Dimension.from_px(span.y), Dimension.from_ch(span.x2), Dimension.from_px(span.y))
    svg.line(Dimension.from_ch(span.x1), Dimension.from_px(span.y-BARHEIGHT), Dimension.from_ch(span.x1), Dimension.from_px(span.y+BARHEIGHT))
    svg.line(Dimension.from_ch(span.x2), Dimension.from_px(span.y-BARHEIGHT), Dimension.from_ch(span.x2), Dimension.from_px(span.y+BARHEIGHT))
    if span.event_x:
        svg.circle(Dimension.from_ch(span.event_x), span.y, PX_EVENT_RADIUS)

    left_text, right_text = span.text
    y = Dimension.from_px(span.y - PX_LINE_TEXT_SEPARATION)
    if left_text and right_text:
        left_x = Dimension.from_ch(span.x1 + INNER_BUFFER)
        svg.text(left_x, y, SVG.XAlign.START, SVG.YAlign.BOTTOM, left_text)
        right_x = Dimension.from_ch(span.x2 - INNER_BUFFER)
        svg.text(right_x, y, SVG.XAlign.END, SVG.YAlign.BOTTOM, right_text)
    elif left_text or right_text:
        x = Dimension.from_ch(span.x1 + (span.x2 - span.x1)/2.0)
        text = left_text or right_text
        svg.text(x, y, SVG.XAlign.MIDDLE, SVG.YAlign.BOTTOM, text)

def chart_to_svg(chart : Chart) -> str:
    svg = SVG(chart.width, chart.height)
    for actor in chart.actors:
        svg_actor(svg, actor)
    for span in chart.spans:
        svg_span(svg, span)
    return svg.render()

#### Driver

def to_span_svg(text_input):
    try:
        operations = parser.parse(text_input)
    except RuntimeError as e:
        return str(e)
    if not operations:
        return ""
    if DEBUG: print(operations)
    spaninfo = operations_to_spans(operations)
    if DEBUG: print(spaninfo)
    chart = spans_to_chart(spaninfo)
    if DEBUG: print(chart)
    svg = chart_to_svg(chart)
    if DEBUG: print(svg)
    return svg