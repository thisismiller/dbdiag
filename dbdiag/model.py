import abc
import dataclasses
from typing import Optional
from . import units

@dataclasses.dataclass
class Actor(object):
    name : str
    slots : units.Slot
    x : units.Ch = None
    y : units.Px = None
    height : units.Px = None

@dataclasses.dataclass
class Operation(object):
    actor : str
    start : int
    end : int
    text : str
    x1 : Optional[units.Ch] = None
    x2 : Optional[units.Ch] = None
    slot : Optional[units.Slot] = None
    y : Optional[units.Px] = None

    def width(self) -> units.Ch:
        return units.Ch(len(self.text))

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

    def width(self) -> units.Ch:
        (left, right) = self.text
        chars = len(left or "") + len(right or "")
        both = left and right
        return units.Ch(chars) + (units.INNER_INNER_BUFFER if both else 0) + units.INNER_BUFFER * 2

@dataclasses.dataclass
class Arrow(object):
    actor : str
    start : int
    end : int
    x1 : Optional[units.Ch] = None
    x2 : Optional[units.Ch] = None
    slot1 : Optional[units.Slot] = None
    slot2 : Optional[units.Slot] = None
    y1 : Optional[units.Px] = None
    y2 : Optional[units.Px] = None

    def width(self) -> units.Ch:
        return 0

@dataclasses.dataclass
class Chart(object):
    actors : list[Actor]
    spans : list[Span]
    cross : list[Span]
