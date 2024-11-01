import abc
import bisect
import textwrap
import dataclasses
import enum
from typing import NamedTuple, Optional, TypeAlias
from . import parser
from . import constants
from . import units
from .units import *

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
    x1 : Optional[units.Ch] = None
    x2 : Optional[units.Ch] = None
    event_x : Optional[units.Ch] = None
    slot : Optional[units.Slot] = None
    y : Optional[units.Px] = None

@dataclasses.dataclass
class SpanStart(object):
    op : str
    start : int
    height : int
    eventpoint : Optional[int] = None

@dataclasses.dataclass
class Actor(object):
    name : str
    slots : units.Slot
    x : units.Ch = None
    y : units.Px = None
    height : units.Px = None

@dataclasses.dataclass
class Chart(object):
    actors : list[Actor]
    spans : list[Span]
    cross : list[Span]

def operations_to_spans(operations : list[parser.Operation]) -> Chart:
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

    if len(inflight) != 0:
        raise RuntimeError(f"Unfinished spans: {','.join(inflight.keys())}")

    actors = [Actor(name, actor_depth[name].max_token()+1) for name in actors_names]
    return Chart(actors, spans, [])

def span_width(span : Span) -> units.Ch:
    (left, right) = span.text
    chars = len(left or "") + len(right or "")
    both = left and right
    return units.Ch(chars) + (INNER_INNER_BUFFER if both else 0) + INNER_BUFFER * 2

def spans_to_chart(chart : Chart) -> Chart:
    base_heights = {}
    current_height = 0
    for actor in chart.actors:
        base_heights[actor.name] = current_height
        current_height += int(actor.slots)

    for span in chart.spans:
        span.x1 = units.Ch(span.start) * OUTER_BUFFER
        span.x2 = span.x1 + span_width(span)
        if span.eventpoint:
            span.event_x = units.Ch(span.eventpoint) * OUTER_BUFFER
        span.slot = units.Slot(base_heights[span.actor] + span.height)

    made_change = True
    while made_change:
        made_change = False
        for span in chart.spans:
            beforeevent = afterevent = None
            for other in chart.spans:
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

    return Chart(chart.actors, chart.spans, chart.cross)

#### Renderer

class Drawable(abc.ABC):
    @abc.abstractmethod
    def x_min(self): pass
    @abc.abstractmethod
    def x_max(self): pass
    @abc.abstractmethod
    def y_min(self): pass
    @abc.abstractmethod
    def y_max(self): pass
    @abc.abstractmethod
    def render(self): pass
    @abc.abstractmethod
    def translate(self, x, y): pass

@dataclasses.dataclass
class Line(Drawable):
    x1 : Dimension
    y1 : Dimension
    x2 : Dimension
    y2 : Dimension
    attrs : Optional[dict[str, str]]

    def x_min(self): return min(self.x1, self.x2)
    def x_max(self): return max(self.x1, self.x2)
    def y_min(self): return min(self.y1, self.y2)
    def y_max(self): return max(self.y1, self.y2)
    def render(self):
        extra = ' '.join([f'{k.replace('_', '-')}="{v}"'  for k,v in self.attrs.items()])
        return f'<line x1="{self.x1}" y1="{self.y1}" x2="{self.x2}" y2="{self.y2}" {extra}/>'
    def translate(self, x : Dimension, y : Dimension):
        self.x1 += x
        self.x2 += x
        self.y1 += y
        self.y2 += y

class XAlign(enum.StrEnum):
    START = "start"
    MIDDLE = "middle"
    END = "end"

class YAlign(enum.StrEnum):
    TOP = "text-top"
    MIDDLE = "middle"
    BOTTOM = "baseline"

@dataclasses.dataclass
class Text(Drawable):
    x : Dimension
    y : Dimension
    xalign : XAlign
    yalign : YAlign
    text : str
    attrs : Optional[dict[str, str]]

    def x_min(self):
        match self.xalign:
            case XAlign.START:
                return self.x
            case XAlign.MIDDLE:
                return self.x - units.Ch(len(self.text)) / 2
            case XAlign.END:
                return self.x - units.Ch(len(self.text))
    def x_max(self):
        match self.xalign:
            case XAlign.START:
                return self.x + units.Ch(len(self.text))
            case XAlign.MIDDLE:
                return self.x + units.Ch(len(self.text)) / 2
            case XAlign.END:
                return self.x
    def y_min(self):
        match self.yalign:
            case YAlign.TOP:
                return self.y
            case YAlign.MIDDLE:
                return self.y - CH_HEIGHT_IN_PX/2
            case YAlign.BOTTOM:
                return self.y - CH_HEIGHT_IN_PX
    def y_max(self):
        match self.yalign:
            case YAlign.TOP:
                return self.y + CH_HEIGHT_IN_PX
            case YAlign.MIDDLE:
                return self.y + CH_HEIGHT_IN_PX/2
            case YAlign.BOTTOM:
                return self.y
    def render(self):
        extra = ' '.join([f'{k.replace('_', '-')}="{v}"'  for k,v in self.attrs.items()])
        return f'<text x="{self.x}" y="{self.y}" text-anchor="{self.xalign}" alignment-baseline="{self.yalign}" {extra}>{self.text}</text>'
    def translate(self, x : Dimension, y : Dimension):
        self.x += x
        self.y += y

@dataclasses.dataclass
class Circle(Drawable):
    x : Dimension
    y : Dimension
    r : Dimension
    attrs : Optional[dict[str, str]]

    # min/max for circles is hard because x can be in ch and y is in px
    # But our use of circles should never determine the boundaries, so
    # being wrong should be fine?
    def x_min(self): return self.x 
    def x_max(self): return self.x 
    def y_min(self): return self.y
    def y_max(self): return self.y
    def render(self):
        extra = ' '.join([f'{k.replace('_', '-')}="{v}"'  for k,v in self.attrs.items()])
        return f'<circle cx="{self.x}" cy="{self.y}" r="{self.r}" {extra}/>'
    def translate(self, x : Dimension, y : Dimension):
        self.x += x
        self.y += y

class SVG(object):
    def __init__(self):
        super()
        self._rendered = None
        self._contents = []
    
    def x_min(self): return min([obj.x_min() for obj in self._contents])
    def x_max(self): return max([obj.x_max() for obj in self._contents])
    def y_min(self): return min([obj.y_min() for obj in self._contents])
    def y_max(self): return max([obj.y_max() for obj in self._contents])
    
    def line(self, x1 : Dimension, y1 : Dimension, x2 : Dimension, y2 : Dimension, **kwargs):
        kwargs.setdefault('stroke', 'black')
        obj = Line(x1, y1, x2, y2, kwargs)
        self._contents.append(obj)
    
    def text(self, x : Dimension, y : Dimension, xalign : XAlign, yalign : YAlign, text : str, **kwargs):
        obj = Text(x, y, xalign, yalign, text, kwargs)
        self._contents.append(obj)

    def circle(self, x : Dimension, y : Dimension, r : Dimension, **kwargs):
        obj = Circle(x, y, r, kwargs)
        self._contents.append(obj)

    def svg(self, x : Dimension, y : Dimension, svg : 'SVG'):
        svg.translate(x, y)
        self._contents.append(svg)

    def translate(self, x : Dimension, y : Dimension):
        for obj in self._contents:
            obj.translate(x, y)

    def render(self):
        if self._rendered:
            return self._rendered
        lines = [obj.render() for obj in self._contents]
        self._rendered = '\n'.join(lines)
        return self._rendered

class RootSVG(SVG):
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

    def render(self):
        body = super().render()
        lines = [self._svg_header(self.x_max(), self.y_max())]
        lines.append(body)
        lines.append(self._svg_footer())
        return '\n'.join(lines)

def actor_to_svg(actor : Actor) -> str:
    svg = SVG()
    svg.text(actor.x, actor.y, XAlign.END, YAlign.MIDDLE, actor.name)
    line_x = actor.x + OUTER_BUFFER
    top_y = actor.y + actor.height/2
    bottom_y = actor.y - actor.height/2
    svg.line(line_x, top_y, line_x, bottom_y)
    return svg

def span_to_svg(span : Span) -> str:
    svg = SVG()
    svg.line(span.x1, span.y, span.x2, span.y)
    svg.line(span.x1, span.y-BARHEIGHT, span.x1, span.y+BARHEIGHT)
    svg.line(span.x2, span.y-BARHEIGHT, span.x2, span.y+BARHEIGHT)
    if span.event_x:
        svg.circle(span.event_x, span.y, PX_EVENT_RADIUS)

    left_text, right_text = span.text
    y = span.y - PX_LINE_TEXT_SEPARATION
    if left_text and right_text:
        left_x = span.x1 + INNER_BUFFER
        svg.text(left_x, y, XAlign.START, YAlign.BOTTOM, left_text)
        right_x = span.x2 - INNER_BUFFER
        svg.text(right_x, y, XAlign.END, YAlign.BOTTOM, right_text)
    elif left_text or right_text:
        x = span.x1 + (span.x2 - span.x1)/2.0
        text = left_text or right_text
        svg.text(x, y, XAlign.MIDDLE, YAlign.BOTTOM, text)
    return svg

def actors_to_slots_px(actors : list[Actor]) -> dict[units.Slot, units.Px]:
    slot = units.Slot(0)
    y = PX_SPAN_VERTICAL
    px_of_slot = {}
    for actor in actors:
        for _ in range(int(actor.slots)):
            px_of_slot[slot] = y
            y += PX_SPAN_VERTICAL
            slot += 1
        y += PX_ACTORBAR_SEPARATION * 2
    return px_of_slot

def chart_to_svg(chart : Chart) -> str:
    svg = RootSVG()

    px_of_slot = actors_to_slots_px(chart.actors)
    spans_of_actor = {}
    for span in chart.spans:
        span.y = px_of_slot[span.slot]
        spans_of_actor.setdefault(span.actor, []).append(span)

    actor_subregions = {}
    for span in chart.spans:
        span_svg = span_to_svg(span)
        subregion = actor_subregions.setdefault(span.actor, SVG())
        subregion.svg(units.Ch(0), units.Px(0), span_svg)

    max_actor_width = max([units.Ch(len(actor.name)) for actor in chart.actors])
    for actor in chart.actors:
        subregion = actor_subregions[actor.name]
        actor.x = max_actor_width
        actor.height = subregion.y_max() - subregion.y_min()
        actor.y = subregion.y_min() + actor.height/2
        actor_svg = actor_to_svg(actor)
        svg.svg(units.Ch(1), 0, actor_svg)
        if constants.GUIDELINES:
            svg.line(units.Percent(0), actor.y-actor.height/2, units.Percent(100), actor.y-actor.height/2, stroke_dasharray="5")
            svg.line(units.Percent(0), actor.y+actor.height/2, units.Percent(100), actor.y+actor.height/2, stroke_dasharray="5")

    spans_x_offset = units.Ch(1) + max_actor_width + OUTER_BUFFER * 2
    for spansvg in actor_subregions.values():
        svg.svg(spans_x_offset, 0, spansvg)
    return svg.render()

#### Driver

def to_span_svg(text_input, embed=None):
    if embed is True or embed is False:
        constants.EMBED = embed
    try:
        operations = parser.parse(text_input)
    except RuntimeError as e:
        return str(e)
    if not operations:
        return ""
    if constants.DEBUG: print(operations)
    chart = operations_to_spans(operations)
    if constants.DEBUG: print(chart)
    chart = spans_to_chart(chart)
    if constants.DEBUG: print(chart)
    svg = chart_to_svg(chart)
    if constants.DEBUG: print(svg)
    return svg