import abc
import textwrap
import enum
import dataclasses
from typing import Optional
from . import units
from . import model
from .units import *

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

def actor_to_svg(actor : model.Actor) -> str:
    svg = SVG()
    svg.text(actor.x, actor.y, XAlign.END, YAlign.MIDDLE, actor.name)
    line_x = actor.x + OUTER_BUFFER
    top_y = actor.y + actor.height/2
    bottom_y = actor.y - actor.height/2
    svg.line(line_x, top_y, line_x, bottom_y)
    return svg

def span_to_svg(span : model.Span) -> str:
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

def actors_to_slots_px(actors : list[model.Actor]) -> dict[units.Slot, units.Px]:
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

def chart_to_svg(chart : model.Chart) -> str:
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