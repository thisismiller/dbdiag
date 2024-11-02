import enum
from . import parser
from . import model
from . import spans
from . import constants
from . import render

class SERIALIZE_AT(enum.StrEnum):
    START = "start"
    END = "end"

def statements_to_operations(statements : list[list[parser.Statement]], serialize_at=SERIALIZE_AT.START) -> model.Chart:
    chart = spans.statements_to_spans(statements)

    operations = []
    for span in chart.spans:
        text = span.text[0] if span.text[1] is None else '->'.join(span.text)
        slot = span.start if serialize_at==SERIALIZE_AT.START else span.end
        slot = span.eventpoint if span.eventpoint is not None else slot
        operations.append(model.Operation(span.actor, slot, slot, text))

    # Renumber the operations so that the start/ends are adjacent
    operations.sort(key=lambda x: x.start)
    for idx, op in enumerate(operations):
        op.start = idx * 2
        op.end = idx * 2 + 1

    # We flattened all slots to 0, so compress the actor also
    for actor in chart.actors:
        actor.slots = 1

    return model.Chart(chart.actors, operations, [])

def to_history_svg(text_input, embed=None, serialize_at=SERIALIZE_AT.START):
    if embed is True or embed is False:
        constants.EMBED = embed
    try:
        statements = parser.parse(text_input)
    except RuntimeError as e:
        return str(e)
    if not statements:
        return ""
    if constants.DEBUG: print(statements)
    chart = statements_to_operations(statements, serialize_at=serialize_at)
    if constants.DEBUG: print(chart)
    render.chart_assign_xs(chart)
    if constants.DEBUG: print(chart)
    svg = render.chart_to_svg(chart)
    if constants.DEBUG: print(svg)
    return svg