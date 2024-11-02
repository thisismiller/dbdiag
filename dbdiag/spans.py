import bisect
import dataclasses
from typing import Optional
from . import parser
from . import constants
from . import units
from . import model
from . import render
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

def operations_to_spans(operations : list[parser.Operation]) -> model.Chart:
    inflight : dict[str, model.SpanStart] = {}
    actors_names : list[str] = []
    actor_depth : dict[str, TokenBucket] = {}
    spans : list[model.Span] = []

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
                inflight[actorkey] = model.SpanStart(op.op, idx, token)
            else:
                start = inflight[actorkey]
                del inflight[actorkey]
                x = idx
                spans.append(model.Span(op.actor, start.start, x, start.height, (start.op, op.op), start.eventpoint))
                actor_depth[op.actor].release(start.height)

    if len(inflight) != 0:
        raise RuntimeError(f"Unfinished spans: {','.join(inflight.keys())}")

    actors = [model.Actor(name, actor_depth[name].max_token()+1) for name in actors_names]
    return model.Chart(actors, spans, [])

def span_width(span : model.Span) -> units.Ch:
    (left, right) = span.text
    chars = len(left or "") + len(right or "")
    both = left and right
    return units.Ch(chars) + (INNER_INNER_BUFFER if both else 0) + INNER_BUFFER * 2

def spans_to_chart(chart : model.Chart) -> model.Chart:
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

    return model.Chart(chart.actors, chart.spans, chart.cross)


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
    svg = render.chart_to_svg(chart)
    if constants.DEBUG: print(svg)
    return svg