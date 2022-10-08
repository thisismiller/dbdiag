#!/usr/bin/env python3

import argparse
import bisect
import collections
import dataclasses
import re
import sys
from typing import NamedTuple, Optional, TypeAlias


class Point(NamedTuple):
    x: int
    y: int = 1  # Set default value
       
UnitsCh : TypeAlias = int
UnitsEm : TypeAlias = int
UnitsPx : TypeAlias = int

# OUTER_BUFFER | INNER_BUFFER <text> INNER_INNER_BUFFER <text> INNER_BUFFER |
INNER_BUFFER : UnitsCh = 1
INNER_INNER_BUFFER : UnitsCh = 3
OUTER_BUFFER : UnitsCh = 4
PX_CHAR_HEIGHT : UnitsPx = 15
PX_SPAN_VERTICAL : UnitsPx = 30
PX_LINE_TEXT_SEPARATION : UnitsPx = 4
BARHEIGHT : UnitsPx = 8
CH_ACTOR_SPAN_SEPARATION : UnitsCh = 6
PX_ACTORBAR_SEPARATION : UnitsPx = 4
PX_EVENT_RADIUS : UnitsPx = 3

DEBUG = False

#### Parser

class Operation(NamedTuple):
    actor: str
    op: str
    key: Optional[str]

def parse_operations(text : str) -> list[Operation]:
    """Parse a text file of operations into list[Operation].

    TEXT := "[^"]+"                           # Quoted strings get " stripped
          | [a-zA-Z0-9_(){},.]+                # Omit " for anything identifier-like
    COMMENT := #.*                            # '#' is still for comments
    SEPERATOR := NOTHING | : | .              # a foo, a: foo() or a.foo are all fine
    OPERATION := TEXT SEPERATOR? TEXT TEXT?   # Becomes: ACTOR seperator OP KEY
    LINE := NOTHING
          | COMMENT
          | OPERATION COMMENT?
    """
    operations = []
    TEXT = r'"[^"]+"|[a-zA-Z0-9_(){}\[\],.]+'
    RGX = f'(?P<actor>{TEXT}) *(:|\.)? *(?P<op>{TEXT}) *(?P<key>{TEXT})? *(#.*)?'
    for line in text.splitlines():
        line = line.strip('\n')
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(RGX, line)
        if not match:
            print(f'Line `{line}` must be of the form `actor: op key`.')
            raise RuntimeError('parse failure')
        opname = match.group('op')
        if opname == 'END':
            opname = None
        if opname == 'EVENT':
            # TODO: There's probably some fancier way to have sentinels
            opname = 'EVENT'
        opname = opname.strip('"') if opname else None
        operations.append(Operation(match.group('actor'), opname, match.group('key')))
    return operations

#### Data Model

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
class SpanStart(object):
    op : str
    start : int
    height : int
    eventpoint : Optional[int] = None

class SpanInfo(NamedTuple):
    spans : list[Span]
    actors : list[str]
    depths : dict[str, TokenBucket]

def operations_to_spans(operations : list[Operation]) -> SpanInfo:
    inflight : dict[str, SpanStart]= {}
    actors_names : list[str] = []
    actor_depth : dict[str, TokenBucket] = {}
    spans : list[Span] = []
    shortspans : int = 0

    for idx, op in enumerate(operations):
        if op.actor not in actors_names:
            actors_names.append(op.actor)
        if op.actor not in actor_depth:
            actor_depth[op.actor] = TokenBucket()

        actorkey = (op.actor, op.key)
        if op.key is None:
            token = actor_depth[op.actor].acquire()
            spans.append(Span(op.actor, idx+shortspans, idx+shortspans+1, token, (op.op, None), None))
            actor_depth[op.actor].release(token)
            shortspans += 1
        elif op.op == 'EVENT':
            inflight[actorkey].eventpoint = idx + shortspans
        elif actorkey not in inflight:
            token = actor_depth[op.actor].acquire()
            inflight[actorkey] = SpanStart(op.op, idx+shortspans, token)
        else:
            start = inflight[actorkey]
            del inflight[actorkey]
            x = idx + shortspans
            spans.append(Span(op.actor, start.start, x, start.height, (start.op, op.op), start.eventpoint))
            actor_depth[op.actor].release(start.height)

    return SpanInfo(spans, actors_names, actor_depth)


class Actor(NamedTuple):
    name : str
    x : int
    y : int
    width : int
    height : int

class Chart(NamedTuple):
    actors : list[Actor]
    spans : list[Span]
    width : UnitsCh
    height : UnitsPx
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
        actor_height = (spaninfo.depths[actor].max_token() + 1) * PX_SPAN_VERTICAL
        actors.append(Actor(actor, actor_x, actor_y, actor_width, actor_height))

        base_heights[actor] = current_height
        current_height += spaninfo.depths[actor].max_token() + 1

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
    return Chart(actors, spaninfo.spans, chart_width, chart_height, max_actor_width)

#### Renderer

def svg_header(width : UnitsCh, height : UnitsPx) -> str:
    return f'''<svg version="1.1" width="{width}ch" height="{height}px" xmlns="http://www.w3.org/2000/svg">'''

def svg_footer() -> str:
    return '</svg>'

def svg_actor(actor : Actor) -> str:
    lines = []
    text_y = actor.y + actor.height / 2
    lines.append(f'<text text-anchor="middle" alignment-baseline="middle" font-family="monospace" x="{actor.x}ch" y="{text_y}px">{actor.name}</text>')
    line_x = actor.x + actor.width + CH_ACTOR_SPAN_SEPARATION / 2
    top_y = actor.y + PX_ACTORBAR_SEPARATION
    bottom_y = actor.y + actor.height - PX_ACTORBAR_SEPARATION
    lines.append(f'<line x1="{line_x}ch" y1="{top_y}px" x2="{line_x}ch" y2="{bottom_y}px" stroke="black" />')
    if DEBUG:
        lines.append(f'<line x1="0%" y1="{top_y}px" x2="100%" y2="{top_y}px" stroke="black" />')
        lines.append(f'<line x1="0%" y1="{bottom_y}px" x2="100%" y2="{bottom_y}px" stroke="black" />')
    return '\n'.join(lines)

def svg_span_line(span : Span) -> str:
    elements = [
        f'<line x1="{span.x1}ch" y1="{span.y}px" x2="{span.x2}ch" y2="{span.y}px" stroke="black" />',
        f'<line x1="{span.x1}ch" y1="{span.y-BARHEIGHT}px" x2="{span.x1}ch" y2="{span.y+BARHEIGHT}px" stroke="black" />',
        f'<line x1="{span.x2}ch" y1="{span.y-BARHEIGHT}px" x2="{span.x2}ch" y2="{span.y+BARHEIGHT}px" stroke="black" />'
    ]
    if span.event_x:
        elements.append(f'<circle cx="{span.event_x}ch" cy="{span.y}" r="{PX_EVENT_RADIUS}" />')
    return '\n'.join(elements)

def svg_span_text(span : Span) -> str:
    left_text, right_text = span.text
    y = span.y - PX_LINE_TEXT_SEPARATION
    if left_text and right_text:
        left_x = span.x1 + INNER_BUFFER
        left = f'<text text-anchor="start" alignment-baseline="baseline" x="{left_x}ch" y="{y}px">{left_text}</text>'
        right_x = span.x2 - INNER_BUFFER
        right = f'<text text-anchor="end" alignment-baseline="baseline" x="{right_x}ch" y="{y}px">{right_text}</text>'
        return left + '\n' + right
    elif left_text or right_text:
        x = span.x1 + (span.x2 - span.x1)/2.0
        text = left_text or right_text
        return f'<text text-anchor="middle" alignment-baseline="baseline" x="{x}ch" y="{y}px">{text}</text>'
    else:
        return ''

def svg_span(span : Span) -> str:
    return svg_span_line(span) + '\n' + svg_span_text(span)

def chart_to_svg(chart : Chart) -> str:
    svg = []
    svg.append(svg_header(chart.width, chart.height))
    for actor in chart.actors:
        svg.append(svg_actor(actor))
    for span in chart.spans:
        svg.append(svg_span(span))
    svg.append(svg_footer())
    return '\n'.join(svg)

#### CLI

def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('file', help='file of operations')
    parser.add_argument('-o', '--output', help='output file path')
    parser.add_argument('--debug', action='store_true')
    return parser.parse_args()

def main(argv):
    args = parse_args(argv)

    if args.debug:
        global DEBUG
        DEBUG = True

    with open(args.file) as f:
        operations = parse_operations(f.read())

    if DEBUG: print(operations)
    spans = operations_to_spans(operations)
    if DEBUG: print(spans)
    chart = spans_to_chart(spans)
    if DEBUG: print(chart)
    svg = chart_to_svg(chart)
    if DEBUG: print(svg)

    if args.output is None or args.output == '-':
        sys.stdout.write(svg)
    elif args.output.endswith('.svg'):
        with open(args.output, 'w') as f:
            f.write(svg)
    elif args.output.endswith('.png'):
        # A yet-to-be-released version of cairosvg is required to correctly
        # render the SVGs produced, so make it a runtime requirement.
        from cairosvg import svg2png
        svg2png(bytestring=svg, write_to=args.output)


if __name__ == '__main__':
    main(sys.argv)
