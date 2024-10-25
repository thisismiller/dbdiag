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

class Arrow(Enum):
    FORWARD = 1
    BACKWARD = 2
    FORWARD_LOST = 3
    BACKWARD_LOST = 4

class Operation(NamedTuple):
    source: str
    arrow: Optional[Arrow]
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


TEXT = r'"[^"]+"|[a-zA-Z0-9_(){}\[\],.]+'

def make_consumer(regex, key):
    rgx = re.compile(regex)
    def consumer(text):
        m = rgx.match(text)
        if m:
            return {key: m.group(key)} if key else {}, text[m.end():]
        else:
            return None
    return consumer

def consume_text(key):
    return make_consumer(f'^(?P<{key}>{TEXT}) *', key)

consume_arrow = make_consumer(r'^(?P<arrow>(->|<-|-x|x-)) *', 'arrow')
consume_separator = make_consumer(r'^(?P<sep> |:|\.) *', 'sep')
consume_eol = make_consumer(r'^(#.*)?$', None)
consume_grouping = make_consumer(r'^(?P<grouping>\[|\]) *', 'grouping')

consume_action = compose(
    consume_text('source'),
    optional(compose(consume_arrow, consume_text('dest'))),
    consume_separator,
    consume_text('op'),
    consume_text('key'))
parser = choose(
    compose(consume_grouping, consume_eol),
    consume_action)


def parse_operations(text : str) -> AST:
    """Parse a text file of operations into List[Operation].

    TEXT := "[^"]+"                           # Quoted strings get " stripped
          | [a-zA-Z0-9_(){},.]+               # Omit " for anything identifier-like
    COMMENT := #.*                            # '#' is still for comments
    ARROW := <- | -> | -x | x-                # Direction of communication
    SEPERATOR := NOTHING | : | .              # a foo, a: foo() or a.foo are all fine
    OPERATION := TEXT (ARROW TEXT)? SEPERATOR? TEXT TEXT?
    GROUPING := [ | ]                         # Concurrent events are in []'s
    LINE := NOTHING
          | COMMENT
          | GROUPING
          | OPERATION COMMENT?
    """

    operations = []
    for line in text.splitlines():
        line = line.strip('\n')
        if not line or line.startswith('#'):
            continue

        result = parser(line)
        if result is None:
            raise RuntimeError('Parse Failure: Line `{line}` must be of the form `actor: op key`.')
        result, _ = result

        if result.get('grouping') and result['grouping'] == '[':
            if grouplist is not None:
                raise RuntimeError('Groupings [] cannot be nested.')
            grouplist = []
            continue
        if result.get('grouping') and result['grouping'] == ']':
            if grouplist is None:
                raise RuntimeError('Unbalanced []. Terminating grouping that was not started.')
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
        operations.append(Operation(result['source'], result.get('arrow'), result.get('dest'), opname, result['key']))
    return operations
