import sys
import argparse
from . import constants
from . import spans

def parse_spans_args(parser=None):
    parser = parser or argparse.ArgumentParser()
    parser.add_argument('file', help='file of operations')
    parser.add_argument('-o', '--output', help='output file path')
    parser.add_argument('--debug', action='store_true', help='print out each intermediate step')
    parser.add_argument('--guidelines', action='store_true', help='add extra lines to debug alignment issues')
    parser.add_argument('--embed', action='store_true', help='only use 12px font and px units')
    return parser

def main_spans(args = None):
    args = args or parse_spans_args().parse_args()

    if args.debug:
        constants.DEBUG = True
    if args.guidelines:
        constants.GUIDELINES = True
    if args.embed:
        constants.EMBED = True

    with open(args.file) as f:
        text_input = f.read()

    svg = spans.to_span_svg(text_input)

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

def parse_main_args(parser=None):
    parser = parser or argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)

    spans_parser = subparsers.add_parser('spans')
    spans_parser.set_defaults(main_func=main_spans)
    parse_spans_args(spans_parser)

    return parser

def main():
    args = parse_main_args().parse_args()
    args.main_func(args)
