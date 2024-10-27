from typing import TypeAlias

UnitsCh : TypeAlias = int
UnitsEm : TypeAlias = int
UnitsPx : TypeAlias = int
UnitsPercent : TypeAlias = int

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
CH_WIDTH_IN_PX = 7

DEBUG = False
EMBED = False