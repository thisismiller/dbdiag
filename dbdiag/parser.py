import re
from enum import Enum
from typing import NamedTuple, Optional, TypeAlias, List

#### Parser

'''
[
A -> B: RPC .B
A -> C: RPC .C
]
[
A <- B: Reply .B
A <- C: Reply .C
]
'''

class Operation(NamedTuple):
    actor: str
    arrow: Optional[str]
    dest: Optional[str]
    op: str
    key: Optional[str]

Grouping : TypeAlias = List[Operation]
AST : TypeAlias = List[Grouping | Operation]

def compose(*args):
    def fn(text):
        state = {}
        for parser in args:
            result = parser(text)
            if result is None:
                return None
            else:
                v, text = result
                state.update(v)
        return state, text
    return fn

def choose(*args):
    def fn(text):
        for parser in args:
            result = parser(text)
            if result is not None:
                return result
        return None
    return fn

def optional(parser):
    def fn(text):
        result = parser(text)
        if result is None:
            return {}, text
        else:
            return result
    return fn


ACTORTEXT = r'"[^"]+"|[a-zA-Z0-9]+'
TEXT = r'"[^"]+"|[a-zA-Z0-9_(){}\[\],.]+'

def make_consumer(regex, key):
    rgx = re.compile(regex)
    def consumer(text):
        m = rgx.match(text)
        if m:
            return {key: m.group(key)} if key else {}, text[m.end():]
        else:
            return None
    consumer.__name__ = 'consume_' + key
    return consumer

def consume_actor(key):
    return make_consumer(f'^(?P<{key}>{ACTORTEXT}) *', key)
def consume_text(key):
    return make_consumer(f'^(?P<{key}>{TEXT}) *', key)
consume_arrow = make_consumer(r'^(?P<arrow>(->|<-|-x|x-)) *', 'arrow')
consume_separator = make_consumer(r'^(?P<sep>[:.]) *', 'sep')
consume_eol = make_consumer(r'^(?P<eol>#.*)?$', 'eol')
consume_grouping = make_consumer(r'^(?P<grouping>[\[\]]) *', 'grouping')

parse_action = compose(
    consume_actor('source'),
    optional(compose(consume_arrow, consume_actor('dest'))),
    consume_separator,
    consume_text('op'),
    optional(consume_text('key')),
    consume_eol)
parse_grouping = compose(
    consume_grouping,
    consume_eol)

parser = choose(parse_grouping, parse_action)


def parse_operations(text : str) -> AST:
    """Parse a text file of operations into List[Operation].

    TEXT := "[^"]+"                           # Quoted strings get " stripped
          | [a-zA-Z0-9_(){},.]+               # Omit " for anything identifier-like
    COMMENT := #.*                            # '#' is still for comments
    ARROW := <- | -> | -x | x-                # Direction of communication
    SEPARATOR := : | .                        # a foo, a: foo() or a.foo are all fine
    OPERATION := TEXT (ARROW TEXT)? SEPARATOR? TEXT TEXT?
    GROUPING := [ | ]                         # Concurrent events are in []'s
    LINE := NOTHING
          | COMMENT
          | GROUPING
          | OPERATION COMMENT?
    """

    operations = []
    grouplist = None
    for line in text.splitlines():
        line = line.strip('\n')
        if not line or line.startswith('#'):
            continue

        result = parser(line)
        if result is None:
            raise RuntimeError('Parse Failure: Line `{line}` must be of the form `actor: op key`.')
        result, _ = result

        if result.get('grouping') == '[':
            if grouplist is not None:
                raise RuntimeError('Groupings [] cannot be nested.')
            print('Starting group')
            grouplist = []
            continue
        if result.get('grouping') == ']':
            if grouplist is None:
                raise RuntimeError('Unbalanced []. Terminating grouping that was not started.')
            print('Ending group')
            operations.append(grouplist)
            grouplist = None
            continue

        opname = result['op']
        if opname == 'END':
            opname = None
        if opname == 'EVENT':
            # TODO: There's probably some fancier way to have sentinels
            opname = 'EVENT'
        opname = opname.strip('"') if opname else None
        operation = Operation(result['source'], result.get('arrow'), result.get('dest'), opname, result.get('key'))
        (grouplist if grouplist is not None else operations).append(operation)
    if grouplist is not None:
        raise RuntimeError('EOF with unbalanced []. Terminating grouping that was not started.')
    return operations
