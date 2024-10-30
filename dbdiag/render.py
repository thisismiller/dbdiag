from . import constants
from typing import TypeAlias

UnitsCh : TypeAlias = int
UnitsEm : TypeAlias = int
UnitsPx : TypeAlias = int
UnitsPercent : TypeAlias = int


class Dimension(object):
    def __init__(self, dist, unit):
        self._dist = dist
        self._unit = unit

    def __str__(self):
        if constants.EMBED and self._unit == 'ch':
            return f'{self._dist * CH_WIDTH_IN_PX._dist}px'
        else:
            return f'{self._dist}{self._unit}'

    def __repr__(self):
        return f'Dimension({self._dist}, {self._unit})'

    def __add__(self, x : 'Dimension') -> 'Dimension':
        match x:
            case int():
                return Dimension(self._dist + x, self._unit)
            case Dimension():
                assert self._unit == x._unit
                return Dimension(self._dist + x._dist, self._unit)
        assert False

    def __radd__(self, x : 'Dimension') -> 'Dimension':
        return self + x

    def __iadd__(self, x : 'Dimension'):
        match x:
            case int():
                self._dist += x
                return self
            case Dimension():
                assert self._unit == x._unit
                self._dist += x._dist
                return self
        assert False

    def __sub__(self, x : 'Dimension') -> 'Dimension':
        match x:
            case int():
                return Dimension(self._dist - x, self._unit)
            case Dimension():
                assert self._unit == x._unit
                return Dimension(self._dist - x._dist, self._unit)
        assert False

    def __rsub__(self, x : 'Dimension') -> 'Dimension':
        match x:
            case int():
                return Dimension(x - self._dist, self._unit)
            case Dimension():
                assert self._unit == x._unit
                return Dimension(x._dist - self._dist, self._unit)
        assert False

    def __isub__(self, x : 'Dimension'):
        match x:
            case int():
                self._dist -= x
                return self
            case Dimension():
                assert self._unit == x._unit
                self._dist -= x._dist
                return self
        assert False

    def __mul__(self, x : 'Dimension') -> 'Dimension':
        match x:
            case int():
                return Dimension(self._dist * x, self._unit)
            case Dimension():
                assert self._unit == x._unit
                return Dimension(self._dist * x._dist, self._unit)
        assert False

    def __rmul__(self, x : 'Dimension') -> 'Dimension':
        return self * x

    def __truediv__(self, x : 'Dimension'):
        match x:
            case int():
                return Dimension(self._dist / x, self._unit)
            case float():
                return Dimension(self._dist / x, self._unit)
            case Dimension():
                assert self._unit == x._unit
                return Dimension(self._dist / x._dist, self._unit)
        assert False

    def __floordiv__(self, x : 'Dimension'):
        match x:
            case int():
                return Dimension(self._dist // x, self._unit)
            case Dimension():
                assert self._unit == x._unit
                return Dimension(self._dist // x._dist, self._unit)
        assert False

    def __lt__(self, x : 'Dimension'):
        match x:
            case int():
                return self._dist < x
            case Dimension():
                assert self._unit == x._unit
                return self._dist < x._dist
        assert False

    def __gt__(self, x : 'Dimension'):
        match x:
            case int():
                return self._dist > x
            case Dimension():
                assert self._unit == x._unit
                return self._dist > x._dist
        assert False

    def __eq__(self, x : 'Dimension'):
        match x:
            case int():
                return self._dist == x
            case Dimension():
                assert self._unit == x._unit
                return self._dist == x._dist
        assert False

    def __neq__(self, x : 'Dimension'):
        match x:
            case int():
                return self._dist != x
            case Dimension():
                assert self._unit == x._unit
                return self._dist != x._dist
        assert False

    @staticmethod
    def from_ch(ch : UnitsCh) -> 'Dimension':
        assert not isinstance(ch, Dimension)
        return Dimension(ch, 'ch')

    @staticmethod
    def from_px(px : UnitsPx) -> 'Dimension':
        assert not isinstance(px, Dimension)
        return Dimension(px, 'px')

    @staticmethod
    def from_percent(p : UnitsPercent) -> 'Dimension':
        assert not isinstance(p, Dimension)
        return Dimension(p, '%')


# OUTER_BUFFER | INNER_BUFFER <text> INNER_INNER_BUFFER <text> INNER_BUFFER |
INNER_BUFFER : Dimension = Dimension.from_ch(1)
INNER_INNER_BUFFER : Dimension = Dimension.from_ch(3)
OUTER_BUFFER : Dimension = Dimension.from_ch(4)
PX_CHAR_HEIGHT : Dimension = Dimension.from_px(15)
PX_SPAN_VERTICAL : Dimension = Dimension.from_px(30)
PX_LINE_TEXT_SEPARATION : Dimension = Dimension.from_px(6)
BARHEIGHT : Dimension = Dimension.from_px(8)
CH_ACTOR_SPAN_SEPARATION : Dimension = Dimension.from_ch(4)
PX_ACTORBAR_SEPARATION : Dimension = Dimension.from_px(3)
PX_EVENT_RADIUS : Dimension = Dimension.from_px(3)
CH_WIDTH_IN_PX : Dimension = Dimension.from_px(7)
CH_HEIGHT_IN_PX : Dimension = Dimension.from_px(12)
