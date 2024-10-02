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
    game_platform_update_options: Any = parser.add_argument_group(
        'flags that can be used with --platforms, --games, or --update'
    )
    game_update_options: Any = parser.add_argument_group(
        'flags that can be used with --games or --update'
    )

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
        help='R|Get all game details from MobyGames that belong to a specific'
        '\nplatform ID, and output the result to files. See flags that can be'
        f'\nused with {Font.b}--games{Font.be} to change this behavior.'
        '\n\n',
    )

    parser.add_argument(
        '-u',
        '--update',
        metavar='<NUMBER_OF_DAYS>',
        type=int,
        help=f'R|Update all the games details for the platforms you\'ve already'
        '\ndownloaded, and output the result to files. See flags that can be'
        f'\nused with {Font.b}--update{Font.be} to change this behavior.'
        '\n\nMobyGames only provides update data for the last 21 days. If'
        '\nyou\'ve waited longer, you should redownload the platform from'
        '\nscratch.'
        '\n\n',
    )

    game_update_options.add_argument(
        '-d',
        '--delimiter',
        metavar='"<DELIMITER>"',
        type=str,
        help=f'R|The single character delimiter to use in the output files. Accepts'
        f'\nsingle-byte characters only. When not specified, defaults to {Font.b}tab{Font.be}.'
        f'\nIgnored if output is set to {Font.b}JSON{Font.be}.'
        '\n\n',
    )

    game_update_options.add_argument(
        '-db',
        '--dropbox',
        action='store_true',
        help='R|ZIP the output files, upload them to Dropbox, and then delete the'
        '\nlocal files.'
        '\n\n',
    )

    game_update_options.add_argument(
        '-fr',
        '--forcerestart',
        action='store_true',
        help='R|Don\'t resume from where MobyDump last left off. Instead, restart'
        '\nthe request process from MobyGames. This deletes your cached files.'
        '\n\n',
    )

    game_update_options.add_argument(
        '-n',
        '--noninteractive',
        action='store_true',
        help='R|Make MobyDump output less chatty for non-interactive terminals, so'
        '\nlogs don\'t get out of control.'
        '\n\n',
    )

    game_update_options.add_argument(
        '-o',
        '--output',
        metavar='<FILE_TYPE_ID>',
        type=int,
        help=f'R|The file type to output to. When not specified, defaults to {Font.b}1{Font.be}.'
        f'\nChoose a number from the following list:'
        '\n\n0 - Don\'t output files'
        '\n1 - Delimiter separated value'
        '\n2 - JSON'
        '\n3 - Delimiter separated value and JSON'
        '\n\nDelimiter separated value files are sanitized for problem'
        '\ncharacters, JSON data is left raw.'
        '\n\n',
    )

    game_update_options.add_argument(
        '-pa',
        '--path',
        metavar='"<FOLDER_PATH>"',
        type=str,
        help='R|The folder to output files to. When not specified, defaults to'
        '\nMobyDump\'s directory.'
        '\n\n',
    )

    game_update_options.add_argument(
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

    game_update_options.add_argument(
        '-r',
        '--ratelimit',
        metavar='<SECONDS_PER_REQUEST>',
        type=int,
        help=f'R|How many seconds to wait between requests. When not specified,'
        f'\ndefaults to {Font.b}10{Font.be}. Overrides the {Font.b}MOBY_RATE{Font.be} environment variable.'
        '\nChoose a number from the following list:'
        '\n\n10 - MobyGames non-commercial free API key'
        '\n5  - MobyPro non-commercial API key'
        '\n\nUse lower numbers at your own risk. Unless you have an agreement'
        '\nwith MobyGames, lower numbers than are suitable for your API key'
        '\ncould get your client or API key banned.'
        '\n\n',
    )

    game_platform_update_options.add_argument(
        '-c',
        '--cache',
        metavar='"<CACHE_PATH>"',
        type=str,
        help=f'R|Change the cache path. Defaults to {Font.b}cache{Font.be} in the same folder'
        '\nMobyDump is in.'
        '\n\n',
    )

    game_platform_update_options.add_argument(
        '-ua',
        '--useragent',
        metavar='"<USER_AGENT>"',
        type=str,
        help=f'R|Change the user agent MobyDump supplies when making requests.'
        '\nDefaults to:'
        f'\n\n{Font.b}MobyDump/{const.__version__}; https://github.com/unexpectedpanda/mobydump{Font.be}'
        '\n\n',
    )

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args: argparse.Namespace = parser.parse_args()

    # Handle incompatible arguments
    if args.platforms and args.games:
        eprint(
            f'Can\'t use {Font.b}--platforms{Font.be} and {Font.b}--games{Font.be} together. Exiting...',
            level='error',
            wrap=False,
        )
        sys.exit(1)

    if args.platforms and args.update:
        eprint(
            f'Can\'t use {Font.b}--platforms{Font.be} and {Font.b}--update{Font.be} together. Exiting...',
            level='error',
            wrap=False,
        )
        sys.exit(1)

    if args.games and args.update:
        eprint(
            f'Can\'t use {Font.b}--games{Font.be} and {Font.b}--update{Font.be} together. Exiting...',
            level='error',
            wrap=False,
        )
        sys.exit(1)

    if args.cache and not (args.games or args.platforms or args.update):
        eprint(
            f'Must specify {Font.b}--games{Font.be}, {Font.b}--platforms{Font.be}, or {Font.b}--update{Font.be} with {Font.b}--cache{Font.be}. Exiting...',
            level='error',
            wrap=False,
        )
        sys.exit(1)

    if args.delimiter and not (args.games or args.update):
        eprint(
            f'Must specify {Font.b}--games{Font.be} or {Font.b}--update{Font.be} with {Font.b}--delimiter{Font.be}. Exiting...',
            level='error',
            wrap=False,
        )
        sys.exit(1)

    if args.output and not (args.games or args.update):
        eprint(
            f'Must specify {Font.b}--games{Font.be} or {Font.b}--update{Font.be} with {Font.b}--output{Font.be}. Exiting...',
            level='error',
            wrap=False,
        )
        sys.exit(1)

    if args.output:
        if args.output > 3 or args.output < 0:
            eprint(
                'Valid file types are 0 (Don\'t output files), 1 (Delimiter separated value), 2 (JSON), or 3 (Delimiter separated value and JSON files). Exiting...',
                level='error',
                indent=0,
            )
            sys.exit(1)

    if args.prefix and not (args.games or args.update):
        eprint(
            f'Must specify {Font.b}--games{Font.be} or {Font.b}--update{Font.be} with {Font.b}--prefix{Font.be}. Exiting...',
            level='error',
            wrap=False,
        )
        sys.exit(1)

    if args.ratelimit and not args.games:
        eprint(
            f'Must specify {Font.b}--games{Font.be} or {Font.b}--update{Font.be} with {Font.b}--ratelimit{Font.be}. Exiting...',
            level='error',
            wrap=False,
        )
        sys.exit(1)

    if args.useragent and not (args.games or args.platforms or args.update):
        eprint(
            f'Must specify {Font.b}--games{Font.be}, {Font.b}--platforms{Font.be}, or {Font.b}--update{Font.be} with {Font.b}--useragent{Font.be}. Exiting...',
            level='error',
            warp=False,
        )
        sys.exit(1)

    if args.update:
        if not 1 <= args.update <= 21:
            eprint('The maximum number of days for updates is 21. Exiting...', level='error')
            sys.exit(1)

    return args
