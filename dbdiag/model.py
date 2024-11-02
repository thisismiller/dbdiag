import dataclasses
from typing import Optional
from . import units

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
