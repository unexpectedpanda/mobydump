import argparse
import sys

from typing import Any

from modules.utils import eprint, Font, SmartFormatter

def user_input() -> argparse.Namespace:
    # Set up ArgParse
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        allow_abbrev=False,
        formatter_class=SmartFormatter,
        add_help=False,
    )

    # Help text order is determined by the group order here
    game_options: Any = parser.add_argument_group('flags that can be used with --games')

    parser.add_argument(
        '-h', '--help', '-?', action='help', default=argparse.SUPPRESS, help=argparse.SUPPRESS
    )

    parser.add_argument(
        '-p', '--platforms',
        action='store_true',
        help='R|Get the platforms and their IDs from MobyGames.'
        '\n\n',
    )

    parser.add_argument(
        '-g', '--games',
        metavar='<PLATFORM_ID>',
        type=int,
        help='R|Get all game details from MobyGames that belong'
        '\nto a specific platform ID.'
        '\n\n',
    )

    game_options.add_argument(
        '-d', '--delimiter',
        metavar='"<DELIMITER>"',
        type=str,
        help=f'R|The single character delimiter to use in the output'
        f'\nfile. Defaults to {Font.b}tab{Font.be}. Ignored if type is set to JSON.'
        '\n\n',
    )

    game_options.add_argument(
        '-o', '--output',
        metavar='"<FILENAME>"',
        type=str,
        help=f'R|The filename to output to. Defaults to {Font.b}output.txt{Font.be}.'
        '\n\n',
    )

    game_options.add_argument(
        '-r', '--ratelimit',
        metavar='<SECONDS_PER_REQUEST>',
        type=str,
        help=f'R|How many seconds to wait between requests. Defaults to {Font.b}10{Font.be}.'
        f'\nChoose from the following list:'
        '\n\n10 - MobyGames non-commercial free API key'
        '\n5  - MobyPro non-commercial API key'
        '\n\nUse lower numbers at your own risk.'
        '\n\n',
    )

    game_options.add_argument(
        '-s', '--startfrom',
        metavar='<OFFSET>',
        type=int,
        help=f'R|The offset to start downloading at. Defaults to {Font.b}0{Font.be}. MobyGames'
        '\nlimits the number of titles returned per requests to 100, so'
        '\nmultiple requests need to be made to retrieve all the titles'
        '\nthat belong to a platform.'
        '\n\nOnly use if downloading was interrupted and you need to'
        '\nrestart at a specific point'
        '\n\n',
    )

    game_options.add_argument(
        '-t', '--type',
        metavar='<FILE_TYPE_ID>',
        type=int,
        help=f'R|The file type to output to. Choose a number from the'
        '\nfollowing list:'
        '\n\n1 - Delimiter Separated Value'
        '\n2 - JSON'
        '\n\n',
    )

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args: argparse.Namespace = parser.parse_args()

    # Handle incompatible arguments
    if args.platforms and args.games:
        eprint('Can\'t use --platforms and --games together. Exiting...', level='error')
        sys.exit(1)

    if args.output and not args.games:
        eprint('Must specify --games with --output. Exiting...', level='error')
        sys.exit(1)

    if args.delimiter and not args.games:
        eprint('Must specify --games with --delimiter. Exiting...', level='error')
        sys.exit(1)

    if args.ratelimit and not args.games:
        eprint('Must specify --games with --ratelimit. Exiting...', level='error')
        sys.exit(1)

    if args.ratelimit:
        if args.ratelimit != 'free' and args.ratelimit != 'pro':
            eprint(f'Valid API key types are {Font.b}free{Font.be} or {Font.b}pro{Font.be}. Exiting...', level='error', indent=0)
            sys.exit(1)

    if args.type and not args.games:
        eprint('Must specify --games with --type. Exiting...', level='error')
        sys.exit(1)

    if args.type:
        if args.type > 2 or args.type < 1:
            eprint('Valid file types are 1 or 2. Exiting...', level='error')
            sys.exit(1)

    return args