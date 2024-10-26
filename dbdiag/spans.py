import bisect
import dataclasses
from typing import NamedTuple, Optional, TypeAlias
from . import parser

UnitsCh : TypeAlias = int
UnitsEm : TypeAlias = int
UnitsPx : TypeAlias = int

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

    depths = {k: v.max_token()+1 for k,v in actor_depth.items()}
    return SpanInfo(spans, actors_names, depths)