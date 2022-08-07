#!/usr/bin/env python3

import argparse
import sys
import collections
import bisect

# OUTER_BUFFER | INNER_BUFFER <text> INNER_INNER_BUFFER <text> INNER_BUFFER |
INNER_BUFFER = 1
INNER_INNER_BUFFER = 3
OUTER_BUFFER = 4
PX_CHAR_HEIGHT = 15
PX_SPAN_VERTICAL = 30
PX_LINE_TEXT_SEPARATION = 4
BARHEIGHT = 8
CH_ACTOR_SPAN_SEPARATION = 6
PX_ACTORBAR_SEPARATION = 4

#### Parser

Operation = collections.namedtuple('Operation', ['actor', 'op', 'key'])

import re

def parse_operations(text):
    operations = []
    TEXT = r'"[^"]+"|[a-zA-Z0-9_(){}.]+'
    RGX = f'(?P<actor>{TEXT}) *(:|\.)? *(?P<op>{TEXT}) *(?P<key>{TEXT})?'
    for line in text.splitlines():
        line = line.strip('\n')
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(RGX, line)
        if not match:
            print(f'Line `{line}` must be of the form `actor: op key`.')
            raise RuntimeError('parse failure')
        opname = match.group('op')
        opname = opname.strip('"')
        if opname == 'END':
            opname = None
        operations.append(Operation(match.group('actor'), opname, match.group('key')))
    return operations

#### Data Model

class Span(object):
    def __init__(self, actor, start, end, height, text):
        self.actor = actor
        self.start = start
        self.end = end
        self.height = height
        self.text = text
        self.x1 = None
        self.x2 = None
        self.y = None

    def __repr__(self):
        return '(%s, %s, %s, %s, %s)' % (repr(self.actor), repr(self.x),
repr(self.y), repr(self.width), repr(self.text))

class TokenBucket(object):
    def __init__(self):
        self._tokens = []
        self._max_token = -1

    def acquire(self):
        if self._tokens:
            token = self._tokens[0]
            self._tokens.pop(0)
        else:
            self._max_token += 1
            token = self._max_token
        return token

    def release(self, token):
        bisect.insort(self._tokens, token)

    def max_token(self):
        return self._max_token

SpanStart = collections.namedtuple('SpanStart', ['op', 'start', 'height'])

SpanInfo = collections.namedtuple('SpanInfo', ['spans', 'actors', 'depths'])

def operations_to_spans(operations):
    inflight = {}
    actors_names = []
    actor_depth = {}
    spans = []
    shortspans = 0

    for idx, op in enumerate(operations):
        if op.actor not in actors_names:
            actors_names.append(op.actor)
        if op.actor not in actor_depth:
            actor_depth[op.actor] = TokenBucket()

        actorkey = (op.actor, op.key)
        if op.key is None:
            token = actor_depth[op.actor].acquire()
            spans.append(Span(op.actor, idx+shortspans, idx+shortspans+1, token, (op.op, None)))
            actor_depth[op.actor].release(token)
            shortspans += 1
            continue
        if actorkey not in inflight:
            token = actor_depth[op.actor].acquire()
            inflight[actorkey] = SpanStart(op.op, idx+shortspans, token)
        else:
            start = inflight[actorkey]
            del inflight[actorkey]
            x = idx + shortspans
            spans.append(Span(op.actor, start.start, x, start.height, (start.op, op.op)))
            actor_depth[op.actor].release(start.height)

    return SpanInfo(spans, actors_names, actor_depth)


Chart = collections.namedtuple('Chart', ['actors', 'spans', 'width',
'height', 'max_actor_width'])
class Actor(object):
    def __init__(self, name, x, y, width, height):
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def __repr__(self):
        return '(%s, %s, %s, %s, %s)' % (repr(self.name), repr(self.x), repr(self.y), repr(self.width), repr(self.height))

def span_width(span):
    (left, right) = span.text
    chars = len(left or "") + len(right or "")
    both = left and right
    ret = chars + (INNER_INNER_BUFFER if both else 0) + INNER_BUFFER * 2
    return ret

def spans_to_chart(spaninfo):
    total_height = sum(v.max_token() for v in spaninfo.depths.values())
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

        span.y = (base_heights[span.actor] + span.height) * PX_SPAN_VERTICAL

    made_change = True
    while made_change:
        made_change = False
        for span in spaninfo.spans:
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

    OFFSET_X = OUTER_BUFFER + max_actor_width + CH_ACTOR_SPAN_SEPARATION
    OFFSET_Y = PX_SPAN_VERTICAL

    for span in spaninfo.spans:
        # adjust to make room for actor panel
        span.x1 += OFFSET_X
        span.x2 += OFFSET_X
        span.y += OFFSET_Y

    chart_width = max(span.x2 for span in spaninfo.spans) + OUTER_BUFFER
    chart_height = current_height * PX_SPAN_VERTICAL + OFFSET_Y + PX_CHAR_HEIGHT
    return Chart(actors, spaninfo.spans, chart_width, chart_height, max_actor_width)

#### Renderer

def svg_header(width, height):
    return f'''<svg version="1.1" width="{width}ch" height="{height}px" xmlns="http://www.w3.org/2000/svg">'''

def svg_footer():
    return '</svg>'

def svg_actor(actor):
    text_y = actor.y + actor.height / 2
    svgtext = f'<text text-anchor="middle" alignment-baseline="middle" font-family="monospace" x="{actor.x}ch" y="{text_y}px">{actor.name}</text>'
    line_x = actor.x + actor.width + CH_ACTOR_SPAN_SEPARATION / 2
    top_y = actor.y + PX_ACTORBAR_SEPARATION
    bottom_y = actor.y + actor.height - PX_ACTORBAR_SEPARATION
    svgline = f'<line x1="{line_x}ch" y1="{top_y}px" x2="{line_x}ch" y2="{bottom_y}px" stroke="black" />'
    return svgtext + '\n' + svgline

def svg_span_line(span):
    return '\n'.join([
        f'<line x1="{span.x1}ch" y1="{span.y}px" x2="{span.x2}ch" y2="{span.y}px" stroke="black" />',
        f'<line x1="{span.x1}ch" y1="{span.y-BARHEIGHT}px" x2="{span.x1}ch" y2="{span.y+BARHEIGHT}px" stroke="black" />',
        f'<line x1="{span.x2}ch" y1="{span.y-BARHEIGHT}px" x2="{span.x2}ch" y2="{span.y+BARHEIGHT}px" stroke="black" />'
    ])

def svg_span_text(span):
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

def svg_span(span):
    return svg_span_line(span) + '\n' + svg_span_text(span)

def chart_to_svg(chart):
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

    with open(args.file) as f:
        operations = parse_operations(f.read())

    if args.debug: print(operations)
    spans = operations_to_spans(operations)
    if args.debug: print(spans)
    chart = spans_to_chart(spans)
    if args.debug: print(chart)
    svg = chart_to_svg(chart)
    if args.debug: print(svg)

    with open(args.output, 'w') as f:
        f.write(svg)

if __name__ == '__main__':
    main(sys.argv)
