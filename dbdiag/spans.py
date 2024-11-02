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
        raise RuntimeError(f"Unfinished spans: {','.join('.'.join(t) for t in inflight.keys())}")

    actors = [model.Actor(name, actor_depth[name].max_token()+1) for name in actors_names]
    return model.Chart(actors, spans, [])

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
    render.chart_assign_xs(chart)
    if constants.DEBUG: print(chart)
    svg = render.chart_to_svg(chart)
    if constants.DEBUG: print(svg)
    return svg