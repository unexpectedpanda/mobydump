import argparse
import sys
from typing import Any

import modules.constants as const
from modules.utils import Font, SmartFormatter, eprint


def user_input() -> argparse.Namespace:
    """
    Gets user input.

    Returns:
        argparse.Namespace: The arguments a user has provided.
    """
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
        '-p',
        '--platforms',
        action='store_true',
        help='R|Get the platforms and their IDs from MobyGames.\n\n',
    )

    parser.add_argument(
        '-g',
        '--games',
        metavar='<PLATFORM_ID>',
        type=int,
        help='R|Get all game details from MobyGames that belong'
        '\nto a specific platform ID.'
        '\n\n',
    )

    game_options.add_argument(
        '-d',
        '--delimiter',
        metavar='"<DELIMITER>"',
        type=str,
        help=f'R|The single character delimiter to use in the output files.'
        f'\nAccepts single-byte characters only. When not specified,'
        f'\ndefaults to {Font.b}tab{Font.be}. Ignored if filetype is set to {Font.b}JSON{Font.be}.'
        '\n\n',
    )

    game_options.add_argument(
        '-f',
        '--filetype',
        metavar='<FILE_TYPE_ID>',
        type=int,
        help=f'R|The file type to output to. When not specified, defaults to {Font.b}1{Font.be}.'
        f'\nChoose a number from the following list:'
        '\n\n1 - Delimiter separated value'
        '\n2 - JSON'
        '\n\nDelimiter separated value files are sanitized for problem characters,'
        '\nJSON data is left raw.'
        '\n\n',
    )

    game_options.add_argument(
        '-pr',
        '--prefix',
        metavar='"<PREFIX>"',
        type=str,
        help=f'R|The prefix to add to the beginning of output filenames. When not'
        '\nspecified, defaults to nothing. By default, the output files are'
        '\nnamed as follows:'
        f'\n\n• {Font.b}Platform name - (Primary) Games.txt{Font.be}'
        f'\n• {Font.b}Platform name - Alternate titles.txt{Font.be}'
        f'\n• {Font.b}Platform name - Genres.txt{Font.be}'
        f'\n• {Font.b}Platform name - Attributes.txt{Font.be}'
        f'\n• {Font.b}Platform name - Releases.txt{Font.be}'
        f'\n• {Font.b}Platform name - Patches.txt{Font.be}'
        f'\n• {Font.b}Platform name - Product codes.txt{Font.be}'
        f'\n• {Font.b}Platform name - Ratings.txt{Font.be}'
        '\n\n',
    )

    game_options.add_argument(
        '-r',
        '--ratelimit',
        metavar='<SECONDS_PER_REQUEST>',
        type=int,
        help=f'R|How many seconds to wait between requests. When not specified,'
        f'\ndefaults to {Font.b}10{Font.be}. Overrides the {Font.b}MOBY_RATE{Font.be} environment variable.'
        '\nChoose a number from the following list:'
        '\n\n10 - MobyGames non-commercial free API key'
        '\n5  - MobyPro non-commercial API key'
        '\n\nUse lower numbers at your own risk. Unless you have an'
        '\nagreement with MobyGames, lower numbers than are suitable for'
        '\nyour API key could get your client or API key banned.'
        '\n\n',
    )

    game_options.add_argument(
        '-u',
        '--useragent',
        metavar='"<USER_AGENT>"',
        type=str,
        help=f'R|Change the user agent MobyDump supplies when making requests.'
        '\nDefaults to:'
        f'\n{Font.b}MobyDump/{const.__version__}; https://github.com/unexpectedpanda/mobydump{Font.be}.'
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

    if args.delimiter and not args.games:
        eprint('Must specify --games with --delimiter. Exiting...', level='error')
        sys.exit(1)

    if args.filetype and not args.games:
        eprint('Must specify --games with --filetype. Exiting...', level='error')
        sys.exit(1)

    if args.filetype:
        if args.filetype > 2 or args.filetype < 1:
            eprint('Valid file types are 1 or 2. Exiting...', level='error')
            sys.exit(1)

    if args.prefix and not args.games:
        eprint('Must specify --games with --prefix. Exiting...', level='error')
        sys.exit(1)

    if args.ratelimit and not args.games:
        eprint('Must specify --games with --ratelimit. Exiting...', level='error')
        sys.exit(1)

    if args.useragent and not (args.games or args.platforms):
        eprint('Must specify --games or --platforms with --useragent. Exiting...', level='error')
        sys.exit(1)

    return args
