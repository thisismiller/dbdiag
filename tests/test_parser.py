import pytest
import textwrap
from dbdiag import parser

def test_one_span_with_end():
    text = textwrap.dedent('''
    S1: W(X) A
    S1: END A
    ''')
    ops = parser.parse_operations(text)
    assert ops == [
        parser.Operation('S1', None, None, 'W(X)', 'A'),
        parser.Operation('S1', None, None, None, 'A')
    ]

def test_one_span():
    text = textwrap.dedent('''
    S1: W(X) A
    S1: 4 A
    ''')
    ops = parser.parse_operations(text)
    assert ops == [
        parser.Operation('S1', None, None, 'W(X)', 'A'),
        parser.Operation('S1', None, None, '4', 'A')
    ]

def test_event():
    text = textwrap.dedent('''
    S1: W(X) A
    S1: EVENT A
    S1: 4 A
    ''')
    ops = parser.parse_operations(text)
    assert ops == [
        parser.Operation('S1', None, None, 'W(X)', 'A'),
        parser.Operation('S1', None, None, 'EVENT', 'A'),
        parser.Operation('S1', None, None, '4', 'A')
    ]