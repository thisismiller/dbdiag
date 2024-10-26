import pytest
import textwrap
import functools
from dbdiag import parser

def parser_test(fn):
    @functools.wraps(fn)
    def testcode():
        text = textwrap.dedent(fn.__doc__)
        expected = fn()
        actual = parser.parse_operations(text)
        assert expected == actual
    return testcode

def parser_test_raises(fn):
    @functools.wraps(fn)
    def testcode():
        with pytest.raises(RuntimeError):
            text = textwrap.dedent(fn.__doc__)
            parser.parse_operations(text)
    return testcode

@parser_test
def test_one_span_with_end():
    '''
    S1: W(X) A
    S1: END A
    '''
    return [
        parser.Operation('S1', None, None, 'W(X)', 'A'),
        parser.Operation('S1', None, None, None, 'A')
    ]

@parser_test
def test_one_span():
    '''
    S1: W(X) A
    S1: 4 A
    '''
    return [
        parser.Operation('S1', None, None, 'W(X)', 'A'),
        parser.Operation('S1', None, None, '4', 'A')
    ]

@parser_test
def test_event():
    '''
    S1: W(X) A
    S1: EVENT A
    S1: 4 A
    '''
    return [
        parser.Operation('S1', None, None, 'W(X)', 'A'),
        parser.Operation('S1', None, None, 'EVENT', 'A'),
        parser.Operation('S1', None, None, '4', 'A')
    ]

@parser_test
def test_separator_dot():
    '''
    T1.R(X) A
    T1.END A
    T1.W(Y) B
    T1.END B
    '''
    return [
        parser.Operation('T1', None, None, 'R(X)', 'A'),
        parser.Operation('T1', None, None, None, 'A'),
        parser.Operation('T1', None, None, 'W(Y)', 'B'),
        parser.Operation('T1', None, None, None, 'B'),
    ]

@parser_test
def test_separator_dot():
    '''
    T1.R(X)
    T1.W(Y)
    '''
    return [
        parser.Operation('T1', None, None, 'R(X)', None),
        parser.Operation('T1', None, None, 'W(Y)', None),
    ]

@parser_test_raises
def test_separator_space():
    '''
    T1 R(X)
    T1 W(Y)
    '''
    pass

@parser_test
def test_arrow():
    '''
    X->Y: R(X) A
    Y->Z: R(X) A.A
    Y<-Z: 4 A.A
    X<-Y: 4 A
    '''
    return [
        parser.Operation('X', '->', 'Y', 'R(X)', 'A'),
        parser.Operation('Y', '->', 'Z', 'R(X)', 'A.A'),
        parser.Operation('Y', '<-', 'Z', '4', 'A.A'),
        parser.Operation('X', '<-', 'Y', '4', 'A'),
    ]

@parser_test
def test_grouping():
    '''
    [
    X: W(A) WA
    X: ok WA
    ]
    '''
    return [
        [parser.Operation('X', None, None, 'W(A)', 'WA'),
         parser.Operation('X', None, None, 'ok', 'WA')],
    ]