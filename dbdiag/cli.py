import sys
import functools
import argparse
from . import constants
from . import spans
from . import history


def make_main(args_fn):
    def outer(body_fn):
        @functools.wraps(body_fn)
        def inner(args=None):
            args = args or args_fn().parse_args()

            if args.debug:
                constants.DEBUG = True
            if args.guidelines:
                constants.GUIDELINES = True
            if args.embed:
                constants.EMBED = True

            with open(args.file) as f:
                text_input = f.read()

            svg = body_fn(text_input, args)

            if args.output is None or args.output == '-':
                sys.stdout.write(svg)
            elif args.output.endswith('.svg'):
                with open(args.output, 'w') as f:
                    f.write(svg)
            elif args.output.endswith('.png'):
                # A yet-to-be-released version of cairosvg is required to correctly
                # render the SVGs produced, so make it a runtime requirement.
                from cairosvg import svg2png
                svg2png(bytestring=svg, write_to=args.output)
        return inner
    return outer

def common_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--debug', action='store_true', help='print out each intermediate step')
    parser.add_argument('--guidelines', action='store_true', help='add extra lines to debug alignment issues')
    parser.add_argument('--embed', action='store_true', help='only use 12px font and px units')
    return parser

def parse_history_args(parser=None):
    parser = parser or argparse.ArgumentParser(parents=[common_parser()])
    parser.add_argument('file', help='file of operations')
    parser.add_argument('-o', '--output', help='output file path')
    parser.add_argument('--serialize-at', default='start', help='start or end')
    return parser


@make_main(parse_history_args)
def main_history(text_input, args):
    return history.to_history_svg(text_input, serialize_at=args.serialize_at)

def parse_spans_args(parser=None):
    parser = parser or argparse.ArgumentParser(parents=[common_parser()])
    parser.add_argument('file', help='file of operations')
    parser.add_argument('-o', '--output', help='output file path')
    return parser

@make_main(parse_spans_args)
def main_spans(text_input, args):
    return spans.to_span_svg(text_input)

def parse_main_args(parser=None):
    common = common_parser()
    parser = parser or argparse.ArgumentParser(parents=[common])
    subparsers = parser.add_subparsers(required=True)

    history_parser = subparsers.add_parser('history', parents=[common])
    history_parser.set_defaults(main_func=main_history)
    parse_history_args(history_parser)

    spans_parser = subparsers.add_parser('spans', parents=[common])
    spans_parser.set_defaults(main_func=main_spans)
    parse_spans_args(spans_parser)

    return parser

def main():
    args = parse_main_args().parse_args()
    args.main_func(args)
