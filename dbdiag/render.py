import abc
import textwrap
import enum
import dataclasses
from typing import Optional
from . import units
from . import model
from .units import *


def chart_assign_xs_old(chart : model.Chart) -> model.Chart:
    base_heights = {}
    current_height = 0
    for actor in chart.actors:
        base_heights[actor.name] = current_height
        current_height += int(actor.slots)

    for span in chart.spans:
        span.x1 = units.Ch(span.start) * OUTER_BUFFER
        span.x2 = span.x1 + span.width()
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
                    span.x2 = max(span.x2, span.x1 + span.width())
                if other.end < span.start and span.x1 < (other.x2 + OUTER_BUFFER):
                    made_change = True
                    span.x1 = other.x2 + OUTER_BUFFER
                    span.x2 = max(span.x2, span.x1 + span.width())
                if other.end < span.end and span.x2 < (other.x2 + OUTER_BUFFER):
                    made_change = True
                    span.x2 = other.x2 + OUTER_BUFFER
                lkj = [['start', 'x1'], ['eventpoint', 'event_x'], ['end', 'x2']]
                for idxattr, xattr in lkj:
                    if span.start-1 == getattr(other, idxattr) and span.x1 > getattr(other, xattr) + OUTER_BUFFER:
                        made_change = True
                        span.x1 = getattr(other, xattr) + OUTER_BUFFER
                        span.x2 = span.x1 + span.width()
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

    return model.Chart(chart.actors, chart.spans, chart.cross)

def chart_assign_xs_generic(chart : model.Chart) -> model.Chart:
    DEBUG_THIS = True
    base_heights = {}
    current_height = 0
    for actor in chart.actors:
        base_heights[actor.name] = current_height
        current_height += int(actor.slots)

    posxattrs = [['start', 'x1'], ['eventpoint', 'event_x'], ['end', 'x2']]

    for span in chart.spans:
        for posattr, xattr in posxattrs:
            if getattr(span, posattr) is not None:
                setattr(span, xattr, units.Ch(getattr(span, posattr)) * OUTER_BUFFER)
        span.x2 = max(span.x2, span.x1 + span.width())
        span.slot = units.Slot(base_heights[span.actor] + span.height)

    made_change = True
    while made_change:
        made_change = False
        for lhs in chart.spans:
            for rhs in chart.spans:
                for lhsposattr, lhsxattr in posxattrs:
                    if getattr(lhs, lhsposattr) is None:
                        continue
                    for rhsposattr, rhsxattr in posxattrs:
                        if getattr(rhs, rhsposattr) is None:
                            continue
                        if getattr(lhs, lhsposattr) < getattr(rhs, rhsposattr) and getattr(lhs, lhsxattr) + lhs.OUTER_BUFFER > getattr(rhs, rhsxattr):
                            made_change = True
                            if DEBUG_THIS: print(f'case=1 lhs.{lhsposattr}={getattr(lhs,lhsposattr)} lhs.{lhsxattr}={getattr(lhs,lhsxattr)} rhs.{rhsposattr}={getattr(rhs,rhsposattr)} rhs.{rhsxattr}={getattr(rhs,rhsxattr)} ')
                            setattr(rhs, rhsxattr, getattr(lhs, lhsxattr) + lhs.OUTER_BUFFER)
                            rhs.x2 = max(rhs.x2, rhs.x1 + rhs.width())
                            if DEBUG_THIS: print(f'case=1 lhs.{lhsposattr}={getattr(lhs,lhsposattr)} lhs.{lhsxattr}={getattr(lhs,lhsxattr)} rhs.{rhsposattr}={getattr(rhs,rhsposattr)} rhs.{rhsxattr}={getattr(rhs,rhsxattr)} ')
                    startgroups = [s for s in chart.spans if rhs.start == s.start]
                    if all(getattr(lhs, lhsposattr) == s.start - 1 and s.x1 > getattr(lhs, lhsxattr) + lhs.OUTER_BUFFER for s in startgroups):
                        made_change = True
                        maxwidth_x2 = max(s.x1 + s.width() for s in startgroups)
                        for s in startgroups:
                            if DEBUG_THIS: print(f'case=2 lhs.{lhsposattr}={getattr(lhs,lhsposattr)} lhs.{lhsxattr}={getattr(lhs,lhsxattr)} s.start={s.start} s.x1={s.x1} ')
                            s.x1 = getattr(lhs, lhsxattr) + lhs.OUTER_BUFFER
                            s.x2 = maxwidth_x2
                            if DEBUG_THIS: print(f'case=2 lhs.{lhsposattr}={getattr(lhs,lhsposattr)} lhs.{lhsxattr}={getattr(lhs,lhsxattr)} s.start={s.start} s.x1={s.x1} ')
                    endgroups = [s for s in chart.spans if rhs.end == s.end]
                    if all(getattr(lhs, lhsposattr) == s.end - 1 and s.x1 + s.width() < s.x2 and s.x2 > getattr(lhs, lhsxattr) + lhs.OUTER_BUFFER for s in endgroups):
                        made_change = True
                        maxwidth_x2 = max(s.x1 + s.width() for s in endgroups)
                        for s in endgroups:
                            if DEBUG_THIS: print(f'case=3 lhs.{lhsposattr}={getattr(lhs,lhsposattr)} lhs.{lhsxattr}={getattr(lhs,lhsxattr)} s.end={s.end} s.x1={s.x1} s.width={s.width()} s.x2={s.x2} maxwidth={maxwidth_x2}')
                            s.x2 = max(maxwidth_x2, getattr(lhs, lhsxattr) + lhs.OUTER_BUFFER)
                            if DEBUG_THIS: print(f'case=3 lhs.{lhsposattr}={getattr(lhs,lhsposattr)} lhs.{lhsxattr}={getattr(lhs,lhsxattr)} s.end={s.end} s.x1={s.x1} s.width={s.width()} s.x2={s.x2} maxwidth={maxwidth_x2}')

def chart_assign_xs_linprog(chart : model.Chart):
    base_heights = {}
    current_height = 0
    for actor in chart.actors:
        base_heights[actor.name] = current_height
        current_height += int(actor.slots)

    max_pos = max(s.end for s in chart.spans) + 1
    baseweights = [0] * max_pos

    # Aim to minimize the total width
    target = baseweights.copy()
    target[max_pos-1] = 1

    inequals = []
    constants = []
    # Ensure each X is separated by at least OUTER_BUFFER
    # x_0 + OUTER_BUFFER <= x_1  ->  x_0 - x_1 <= -OUTER_BUFFER
    for idx in range(max_pos-1):
        ineq = baseweights.copy()
        ineq[idx] = 1
        ineq[idx+1] = -1
        inequals.append(ineq)
        outer_buffer = max(s.OUTER_BUFFER for s in chart.spans if s.start==idx or s.end==idx or s.eventpoint==idx)
        constants.append(-int(outer_buffer))
    
    # Now add the constraints for the widths
    # x_0 + width >= x1  ->  x_0 - x1 >= width  ->  x1 - x0 <= width
    for span in chart.spans:
        ineq = baseweights.copy()
        ineq[span.start] = -1
        ineq[span.end] = 1
        inequals.append(ineq)
        constants.append(int(span.width()))
    
    # Bounds is always (0, infinity)
    x_bounds = [(0, None)] * max_pos
    # Integer variable; decision variable must be an integer within bounds.
    integrality = [1] * max_pos

    for weights, const in zip(inequals, constants):
        lhs = ' + '.join([str(weight) + '*x_' + str(idx) for idx,weight in enumerate(weights) if weight != 0])
        print(f'{lhs} <= {const}')

    import scipy.optimize
    result = scipy.optimize.linprog(target, A_ub=inequals, b_ub=constants, bounds=x_bounds, integrality=integrality)
    print(result)

    pos_to_ch = baseweights.copy()
    for idx, val in enumerate(result.x):
        pos_to_ch[idx] = units.Ch(int(val))
    
    posxattrs = [['start', 'x1'], ['eventpoint', 'event_x'], ['end', 'x2']]
    for span in chart.spans:
        for posattr, xattr in posxattrs:
            if getattr(span, posattr) is not None:
                setattr(span, xattr, pos_to_ch[getattr(span, posattr)])
        span.slot = units.Slot(base_heights[span.actor] + span.height)

def chart_assign_xs_shittylinprog(chart : model.Chart):
    DEBUG_THIS = False
    base_heights = {}
    current_height = 0
    for actor in chart.actors:
        base_heights[actor.name] = current_height
        current_height += int(actor.slots)

    max_pos = max(s.end for s in chart.spans) + 1
    constraints = {}

    for idx in range(max_pos-1):
        outer_buffer = max(s.OUTER_BUFFER for s in chart.spans if s.start==idx or s.end==idx or s.eventpoint==idx)
        constraints[(idx, idx+1)] = int(outer_buffer)
    for span in chart.spans:
        constraints[(span.start, span.end)] = int(span.width())

    xs = [0] * max_pos
    made_change = True
    while made_change:
        made_change = False
        for (start,end), v in constraints.items():
            if xs[end] - xs[start] < v:
                made_change = True
                if DEBUG_THIS: print(f'xs[{start}]={xs[start]} xs[{end}]={xs[end]} after={v}')
                xs[end] = xs[start] + v

    pos_to_ch = [units.Ch(0)] * max_pos
    for idx, val in enumerate(xs):
        pos_to_ch[idx] = units.Ch(int(val))

    posxattrs = [['start', 'x1'], ['eventpoint', 'event_x'], ['end', 'x2']]
    for span in chart.spans:
        for posattr, xattr in posxattrs:
            if getattr(span, posattr) is not None:
                setattr(span, xattr, pos_to_ch[getattr(span, posattr)])
        span.slot = units.Slot(base_heights[span.actor] + span.height)
    

chart_assign_xs = chart_assign_xs_shittylinprog

class Renderable(abc.ABC):
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
class Line(Renderable):
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
class Text(Renderable):
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
class Circle(Renderable):
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
        lines = [self._svg_header(self.x_max() + units.Ch(1), self.y_max() + PX_ACTORBAR_SEPARATION*2)]
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

def operation_to_svg(op : model.Operation) -> SVG:
    svg = SVG()
    mid_x = (op.x1 + op.x2)/2
    svg.text(mid_x, op.y, XAlign.MIDDLE, YAlign.BOTTOM, op.text)
    return svg

def span_to_svg(span : model.Span) -> str:
    svg = SVG()
    svg.line(span.x1, span.y, span.x2, span.y)
    svg.line(span.x1, span.y-BARHEIGHT, span.x1, span.y+BARHEIGHT)
    svg.line(span.x2, span.y-BARHEIGHT, span.x2, span.y+BARHEIGHT)
    if span.event_x is not None:
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
    y = PX_CHAR_HEIGHT + PX_LINE_TEXT_SEPARATION
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
        match span:
            case model.Operation():
                span_svg = operation_to_svg(span)
            case model.Span():
                span_svg = span_to_svg(span)
            case _:
                assert False
        subregion = actor_subregions.setdefault(span.actor, SVG())
        subregion.svg(units.Ch(0), units.Px(0), span_svg)

    show_actors = len(chart.actors) > 1 or chart.actors[0].name != ""
    max_actor_width = max([units.Ch(len(actor.name)) for actor in chart.actors])
    for actor in chart.actors:
        subregion = actor_subregions[actor.name]
        actor.x = max_actor_width
        actor.height = subregion.y_max() - subregion.y_min()
        actor.y = subregion.y_min() + actor.height/2
        actor_svg = actor_to_svg(actor)
        if show_actors:
            svg.svg(units.Ch(1), 0, actor_svg)
        if constants.GUIDELINES:
            svg.line(units.Percent(0), actor.y-actor.height/2, units.Percent(100), actor.y-actor.height/2, stroke_dasharray="5")
            svg.line(units.Percent(0), actor.y+actor.height/2, units.Percent(100), actor.y+actor.height/2, stroke_dasharray="5")

    spans_x_offset = units.Ch(1)
    if show_actors:
        spans_x_offset += max_actor_width + OUTER_BUFFER * 2
    for spansvg in actor_subregions.values():
        svg.svg(spans_x_offset, 0, spansvg)
    return svg.render()