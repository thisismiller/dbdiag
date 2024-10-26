import pytest
import textwrap
import functools
from dbdiag import parser, spans

def spans_test(fn):
    @functools.wraps(fn)
    def testcode():
        text = textwrap.dedent(fn.__doc__)
        expected = fn()
        actual = parser.parse_operations(text)
        actual = spans.operations_to_spans(actual)
        assert expected == actual
    return testcode

def spans_test_raises(fn):
    @functools.wraps(fn)
    def testcode():
        with pytest.raises(RuntimeError):
            text = textwrap.dedent(fn.__doc__)
            ast = parser.parse_operations(text)
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