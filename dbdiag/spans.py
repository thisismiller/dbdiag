import bisect
import textwrap
import dataclasses
import enum
from typing import NamedTuple, Optional, TypeAlias
from . import parser
from . import constants
from .render import *

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


class Actor(NamedTuple):
    name : str
    x : Dimension
    y : Dimension
    width : Dimension
    height : Dimension

Drawable : TypeAlias = Span

class Chart(NamedTuple):
    actors : list[Actor]
    spans : list[Drawable]
    width : Dimension
    height : Dimension

def span_width(span : Span) -> Dimension:
    (left, right) = span.text
    chars = len(left or "") + len(right or "")
    both = left and right
    return Dimension.from_ch(chars) + (INNER_INNER_BUFFER if both else 0) + INNER_BUFFER * 2

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
        span.x1 = Dimension.from_ch(span.start) * OUTER_BUFFER
        span.x2 = span.x1 + span_width(span)
        if span.eventpoint:
            span.event_x = Dimension.from_ch(span.eventpoint) * OUTER_BUFFER

        span.y = Dimension.from_px(base_heights[span.actor] + span.height) * PX_SPAN_VERTICAL

    made_change = True
    while made_change:
        made_change = False
        for span in spaninfo.spans:
            beforeevent = afterevent = None
            for other in spaninfo.spans:
                if other.start < span.start and span.x1 < (other.x1 + OUTER_BUFFER):
                    made_change = True
                    span.x1 = other.x1 + OUTER_BUFFER
                    span.x2 = max(span.x2, span.x1 + span_width(span))
                if other.end < span.start and span.x1 < (other.x2 + OUTER_BUFFER):
                    made_change = True
                    span.x1 = other.x2 + OUTER_BUFFER
                    span.x2 = max(span.x2, span.x1 + span_width(span))
                if other.end < span.end and span.x2 < (other.x2 + OUTER_BUFFER):
                    made_change = True
                    span.x2 = other.x2 + OUTER_BUFFER
                lkj = [['start', 'x1'], ['eventpoint', 'event_x'], ['end', 'x2']]
                for idxattr, xattr in lkj:
                    if span.start-1 == getattr(other, idxattr) and span.x1 > getattr(other, xattr) + OUTER_BUFFER:
                        made_change = True
                        span.x1 = getattr(other, xattr) + OUTER_BUFFER
                        span.x2 = span.x1 + span_width(span)
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
        span.y += [a.name for a in actors].index(span.actor) * PX_ACTORBAR_SEPARATION
        if span.event_x:
            span.event_x += OFFSET_X
    for idx, actor in enumerate(actors):
        actors[idx] = actor._replace(y=actor.y + idx * PX_ACTORBAR_SEPARATION)

    chart_width = max(span.x2 for span in spaninfo.spans) + OUTER_BUFFER
    chart_height = current_height * PX_SPAN_VERTICAL + OFFSET_Y
    return Chart(actors, spaninfo.spans, chart_width, chart_height)

#### Renderer

class SVG(object):
    class XAlign(enum.StrEnum):
        START = "start"
        MIDDLE = "middle"
        END = "end"

    class YAlign(enum.StrEnum):
        TOP = "text-top"
        MIDDLE = "middle"
        BOTTOM = "baseline"

    def _svg_header(self, width : Dimension, height : Dimension) -> str:
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
        if constants.EMBED:
            header += textwrap.dedent("""
                text {
                    font-size: 12px;
                    font-family: monospace;
                }""")
        header += textwrap.dedent("""
                </style>
            </defs>""")
        return header

    def _svg_footer(self) -> str:
        return '</svg>'

    def __init__(self, width : Dimension, height : Dimension):
        super()
        self._width = width
        self._height = height
        self._svg = [self._svg_header(self._width, self._height)]
        self._rendered = None
    
    def line(self, x1 : Dimension, y1 : Dimension, x2 : Dimension, y2 : Dimension, **kwargs):
        extra = ' '.join([f'{k.replace('_', '-')}="{v}"'  for k,v in kwargs.items()])
        self._svg.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="black" {extra}/>'
        )
    
    def text(self, x : Dimension, y : Dimension, xalign : XAlign, yalign : YAlign, text : str, **kwargs):
        extra = ' '.join([f'{k.replace('_', '-')}="{v}"'  for k,v in kwargs.items()])
        self._svg.append(
            f'<text x="{x}" y="{y}" text-anchor="{xalign}" alignment-baseline="{yalign}" {extra}>{text}</text>'
        )

    def circle(self, x : Dimension, y : Dimension, r : Dimension):
        self._svg.append(
            f'<circle cx="{x}" cy="{y}" r="{r}" />'
        )

    def render(self):
        if self._rendered:
            return self._rendered
        self._svg.append(self._svg_footer())
        self._rendered = '\n'.join(self._svg)
        return self._rendered

def svg_actor(svg : SVG, actor : Actor) -> str:
    lines = []
    text_x = actor.x + actor.width
    text_y = actor.y + actor.height / 2
    svg.text(text_x, text_y, SVG.XAlign.END, SVG.YAlign.MIDDLE, actor.name, font_family="monospace")
    line_x = actor.x + actor.width + CH_ACTOR_SPAN_SEPARATION / 2
    top_y = actor.y + PX_ACTORBAR_SEPARATION
    bottom_y = actor.y + actor.height - PX_ACTORBAR_SEPARATION
    svg.line(line_x, top_y, line_x, bottom_y)
    if constants.GUIDELINES:
        svg.line(Dimension.from_percent(0), top_y, Dimension.from_percent(100), top_y, stroke_dasharray="5")
        svg.line(Dimension.from_percent(0), bottom_y, Dimension.from_percent(100), bottom_y, stroke_dasharray="5")
    return '\n'.join(lines)

def svg_span(svg : SVG, span : Span) -> str:
    svg.line(span.x1, span.y, span.x2, span.y)
    svg.line(span.x1, span.y-BARHEIGHT, span.x1, span.y+BARHEIGHT)
    svg.line(span.x2, span.y-BARHEIGHT, span.x2, span.y+BARHEIGHT)
    if span.event_x:
        svg.circle(span.event_x, span.y, PX_EVENT_RADIUS)

    left_text, right_text = span.text
    y = span.y - PX_LINE_TEXT_SEPARATION
    if left_text and right_text:
        left_x = span.x1 + INNER_BUFFER
        svg.text(left_x, y, SVG.XAlign.START, SVG.YAlign.BOTTOM, left_text)
        right_x = span.x2 - INNER_BUFFER
        svg.text(right_x, y, SVG.XAlign.END, SVG.YAlign.BOTTOM, right_text)
    elif left_text or right_text:
        x = span.x1 + (span.x2 - span.x1)/2.0
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
    if constants.DEBUG: print(operations)
    spaninfo = operations_to_spans(operations)
    if constants.DEBUG: print(spaninfo)
    chart = spans_to_chart(spaninfo)
    if constants.DEBUG: print(chart)
    svg = chart_to_svg(chart)
    if constants.DEBUG: print(svg)
    return svg