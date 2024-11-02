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

@dataclasses.dataclass
class SpanStart(object):
    op : str
    start : int
    height : int
    eventpoint : Optional[int] = None

def statements_to_spans(statements : list[parser.Statement]) -> model.Chart:
    inflight : dict[str, SpanStart] = {}
    actors_names : list[str] = []
    actor_depth : dict[str, TokenBucket] = {}
    spans : list[model.Span] = []

    for idx, group in enumerate(statements):
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
                spans.append(model.Span(op.actor, start.start, x, start.height, (start.op, op.op), start.eventpoint))
                actor_depth[op.actor].release(start.height)

    if len(inflight) != 0:
        raise RuntimeError(f"Unfinished spans: {','.join(inflight.keys())}")

    actors = [model.Actor(name, actor_depth[name].max_token()+1) for name in actors_names]
    return model.Chart(actors, spans, [])

def spans_to_chart(chart : model.Chart) -> model.Chart:
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

def chart_assign_xs(chart : model.Chart) -> model.Chart:
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
                        if getattr(lhs, lhsposattr) < getattr(rhs, rhsposattr) and getattr(lhs, lhsxattr) + OUTER_BUFFER > getattr(rhs, rhsxattr):
                            made_change = True
                            #print(f'case=1 lhs.{lhsposattr}={getattr(lhs,lhsposattr)} lhs.{lhsxattr}={getattr(lhs,lhsxattr)} rhs.{rhsposattr}={getattr(rhs,rhsposattr)} rhs.{rhsxattr}={getattr(rhs,rhsxattr)} ')
                            setattr(rhs, rhsxattr, getattr(lhs, lhsxattr) + OUTER_BUFFER)
                            rhs.x2 = max(rhs.x2, rhs.x1 + rhs.width())
                    if getattr(lhs, lhsposattr) == rhs.start - 1 and rhs.x1 > getattr(lhs, lhsxattr) + OUTER_BUFFER:
                        made_change = True
                        #rhsposattr = 'start' ; rhsxattr = 'x1'
                        #print(f'case=2 lhs.{lhsposattr}={getattr(lhs,lhsposattr)} lhs.{lhsxattr}={getattr(lhs,lhsxattr)} rhs.{rhsposattr}={getattr(rhs,rhsposattr)} rhs.{rhsxattr}={getattr(rhs,rhsxattr)} ')
                        rhs.x1 = getattr(lhs, lhsxattr) + OUTER_BUFFER
                        rhs.x2 = rhs.x1 + rhs.width()
                    #rhsposattr = 'end' ; rhsxattr = 'x2'
                    #print(f'case=3a lhs.{lhsposattr}={getattr(lhs,lhsposattr)} lhs.{lhsxattr}={getattr(lhs,lhsxattr)} rhs.{rhsposattr}={getattr(rhs,rhsposattr)} rhs.{rhsxattr}={getattr(rhs,rhsxattr)} rhs.x1={rhs.x1} rhs.width={rhs.width()}')
                    if getattr(lhs, lhsposattr) == rhs.end - 1 and rhs.x1 + rhs.width() < rhs.x2 and rhs.x2 > getattr(lhs, lhsxattr) + OUTER_BUFFER:
                        made_change = True
                        #rhsposattr = 'end' ; rhsxattr = 'x2'
                        #print(f'case=3 lhs.{lhsposattr}={getattr(lhs,lhsposattr)} lhs.{lhsxattr}={getattr(lhs,lhsxattr)} rhs.{rhsposattr}={getattr(rhs,rhsposattr)} rhs.{rhsxattr}={getattr(rhs,rhsxattr)} rhs.x1={rhs.x1} rhs.width={rhs.width()}')
                        rhs.x2 = max(rhs.x1 + rhs.width(), getattr(lhs, xattr) + OUTER_BUFFER)

#### Driver

def to_span_svg(text_input, embed=None):
    if embed is True or embed is False:
        constants.EMBED = embed
    try:
        statements = parser.parse(text_input)
    except RuntimeError as e:
        return str(e)
    if not statements:
        return ""
    if constants.DEBUG: print(statements)
    chart = statements_to_spans(statements)
    if constants.DEBUG: print(chart)
    chart_assign_xs(chart)
    if constants.DEBUG: print(chart)
    svg = render.chart_to_svg(chart)
    if constants.DEBUG: print(svg)
    return svg