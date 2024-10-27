import pytest
import textwrap
import functools
from dbdiag import parser, spans

def spans_test(fn):
    @functools.wraps(fn)
    def testcode():
        text = textwrap.dedent(fn.__doc__)
        expected = fn()
        actual = parser.parse(text)
        actual = spans.operations_to_spans(actual)
        assert expected == actual
    return testcode

def spans_test_raises(fn):
    @functools.wraps(fn)
    def testcode():
        with pytest.raises(RuntimeError):
            text = textwrap.dedent(fn.__doc__)
            ast = parser.parse(text)
            spans.operations_to_spans(ast)
    return testcode

@spans_test
def test_spans():
    '''
    A: W(A) A
    A: ok A
    '''
    return spans.SpanInfo([
        spans.Span('A', 0, 1, 0, ('W(A)', 'ok'), None)
    ], ['A'], {'A': 1})

@spans_test
def test_short_spans():
    '''
    A: W(X)
    B: R(X)
    '''
    return spans.SpanInfo([
        spans.Span('A', 0, 1, 0, ('W(X)', None), None),
        spans.Span('B', 2, 3, 0, ('R(X)', None), None)
    ], ['A', 'B'], {'A': 1, 'B': 1})

@spans_test
def test_groups():
    '''
    [
    A: W(A) A
    B: W(B) B
    ]
    A: ok A
    B: ok B
    '''
    return spans.SpanInfo([
        spans.Span('A', 0, 1, 0, ('W(A)', 'ok'), None),
        spans.Span('B', 0, 2, 0, ('W(B)', 'ok'), None)
    ], ['A', 'B'], {'A': 1, 'B': 1})