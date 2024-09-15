#!/usr/bin/env python

"""
MobyDump downloads data from the MobyGames API for a specific platform, and outputs it to
a delimiter-separated value file or JSON.

https://github.com/unexpectedpanda/mobydump
"""
import datetime
import html
import json
import os
import pathlib
import sys

from dotenv import load_dotenv  # type: ignore

import modules.constants as const
from modules.get_mg_data import (
    delete_cache,
    get_game_details,
    get_games,
    get_platforms,
    get_updates,
    write_output_files,
)
from modules.input import user_input
from modules.requests import request_wait
from modules.utils import Config, Font, eprint, old_windows

# Enable VT100 escape sequence for Windows 10+
if not old_windows() and sys.platform.startswith('win'):
    from modules.utils import enable_vt_mode

    enable_vt_mode()

# Require at least Python 3.10.
try:
    assert sys.version_info >= (3, 10)
except Exception:
    eprint(
        f'You need Python 3.10 or higher to run MobyDump. You are running Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}',
        level='error',
    )
    sys.exit()

# Get the contents of the .env file
load_dotenv()


def main() -> None:
    if os.getenv('MOBY_API'):
        eprint('\n', wrap=False)
        eprint(r' /~~~~~~~~~~~~~)', wrap=False)
        eprint(r'(                )', wrap=False)
        eprint(r'\        (o)      )', wrap=False)
        eprint(r' \______/          )', wrap=False)
        eprint(r'     \____          )', wrap=False)
        eprint(r'    ___ __\       )', wrap=False)
        eprint(r'   /_/\_\____    )  ', wrap=False)
        eprint(r'   __       /  /', wrap=False)
        eprint(r'   \ \_____/  /', wrap=False)
        eprint(r'   / ________/   ', wrap=False)
        eprint(f'  /_/ MOBYDUMP {const.__version__}\n', wrap=False)

        # Get user input
        args = user_input()

        # Get the API key
        api_key: str = html.escape(str(os.getenv('MOBY_API')))

        # Set the user agent
        user_agent: str = f'MobyDump/{const.__version__}; https://www.retro-exo.com/'

        if args.useragent:
            user_agent = str(args.useragent)

        # Set the rate limit
        rate_limit: int = 10

        if os.getenv('MOBY_RATE'):
            rate_limit = int(os.getenv('MOBY_RATE'))  # type: ignore

        if args.ratelimit:
            rate_limit = args.ratelimit

        # Set the output file type
        output_file_type: int = 1

        if args.output is not None:
            output_file_type = args.output

        # Set the output path
        output_path: str = ''

        if args.path:
            output_path = args.path

        # Set the prefix
        prefix: str = ''

        if args.prefix:
            prefix = args.prefix

        # Set the delimiter
        delimiter: str = '\t'

        if args.delimiter:
            delimiter = args.delimiter

            encoded_delimiter: str = bytearray(delimiter, encoding='utf-8').decode('unicode_escape')

            # Deal with escaped characters like \t
            if delimiter.startswith('\\'):
                delimiter = encoded_delimiter

            # Microsoft Access only really likes ASCII delimiters and so does Pandas' to_csv function,
            # so limit characters to single byte
            if len(encoded_delimiter) > 1:
                eprint(
                    f'Delimiter is more than one byte long in unicode ({delimiter} = '
                    f'{delimiter.encode('utf-8')!r}). Choose another character. Exiting...',
                    level='error',
                    indent=0,
                )
                sys.exit(1)

        # Set the request headers
        headers: dict[str, str] = {'Accept': 'application/json', 'User-Agent': user_agent}

        # Create the config object instance
        config: Config = Config(
            args, api_key, rate_limit, headers, output_file_type, output_path, prefix, delimiter
        )

        # ================================================================================
        # Get platforms if requested by the user
        # ================================================================================

        if args.platforms:
            platforms = get_platforms(config)

            # Sort the response by name
            platform_list: list[dict[str, str | int]] = sorted(
                platforms['platforms'], key=lambda d: d['platform_name']
            )

            # Get the longest platform name length for column formatting
            platform_width: int = max(
                [len(str(x['platform_name'])) for x in platforms['platforms']]
            )

            # Print the platforms
            eprint(f'\n{Font.b}{Font.u}{"NAME":<{platform_width+4}}{"ID":>5}{Font.end}\n')
            for platform in platform_list:
                eprint(
                    f'{platform["platform_name"]:<{platform_width+4}}{platform["platform_id"]!s:>5}',
                    wrap=False,
                )

            sys.exit(0)

        # ================================================================================
        # Get games if requested by the user
        # ================================================================================
        if args.games:
            # Set the platform
            platform_id: int = args.games

            # Get the platform name if we know it already
            platform_name: str = f'platform {platform_id!s}'
            raw_platform_name: str = ''

            if not pathlib.Path('cache/platforms.json').is_file():
                get_platforms(config)
                request_wait(config.rate_limit)

            with open(pathlib.Path('cache/platforms.json'), encoding='utf-8') as platform_cache:
                cached_platforms = json.load(platform_cache)

                for cached_platform in cached_platforms['platforms']:
                    if cached_platform['platform_id'] == platform_id:
                        platform_name = (
                            f'the {Font.b}{cached_platform["platform_name"]}{Font.be} platform'
                        )

                        raw_platform_name = cached_platform['platform_name']

            # Set up the cache folders
            pathlib.Path(f'cache/{platform_id}/games').mkdir(parents=True, exist_ok=True)
            pathlib.Path(f'cache/{platform_id}/games-details').mkdir(parents=True, exist_ok=True)

            # Read the requests status file if it exists
            now = (
                datetime.datetime.now(tz=datetime.timezone.utc)
                .replace(tzinfo=datetime.timezone.utc)
                .astimezone(tz=None)
            )

            completion_status: dict[str, bool | str] = {
                'stage_1_finished': False,
                'stage_2_finished': False,
                'last_updated': now.strftime("%Y/%m/%d"),
            }

            if pathlib.Path(f'cache/{platform_id}/status.json').is_file():
                with open(
                    pathlib.Path(f'cache/{platform_id}/status.json'), encoding='utf-8'
                ) as status_cache:
                    try:
                        completion_status = json.load(status_cache)
                    except Exception:
                        pass

            # If everything has already been downloaded, ask the user if they want to redownload or write out from
            # cache.
            resume: str = ''

            if not args.forcerestart:
                if completion_status['stage_1_finished'] and completion_status['stage_2_finished']:
                    while resume != 'r' and resume != 'w' and resume != 'q':
                        eprint(
                            f'\nGames from {platform_name} have already been downloaded. Do you want to redownload (r), '
                            'write new output files from cache (w), or exit (q)?',
                            level='warning',
                            indent=0,
                        )
                        resume = input('\n> ')
                        eprint('')

            if resume == 'r' or args.forcerestart:
                completion_status = delete_cache(platform_id)
            elif resume == 'q':
                sys.exit()

            # Stage 1: Download games for the platform
            if not completion_status['stage_1_finished']:
                get_games(platform_id, platform_name, completion_status, config)

            # Stage 2: Download individual game details
            if not completion_status['stage_2_finished']:
                get_game_details(platform_id, completion_status, config)

            # Write the output files
            write_output_files(config, platform_id, raw_platform_name)

        # ================================================================================
        # Get updates if requested by the user
        # ================================================================================

        # Set up the cache folder
        pathlib.Path('cache/updates').mkdir(parents=True, exist_ok=True)

        if config.args.update:
            get_updates(config)
    else:
        eprint(
            '\nMobyDump needs a MobyGames API key to continue. To add one:'
            f'\n\n1. Create a file named {Font.b}.env{Font.be} in the same folder MobyDump is '
            'in.'
            '\n2. Add your MobyGames API key as follows, replacing '
            '\n   <MOBYGAMES_API_KEY> with your API key:'
            '\n\nMOBY_API="<MOBYGAMES_API_KEY>"'
            '\n\nExiting...',
            level='error',
            indent=0,
            wrap=False,
        )

    sys.exit(1)


if __name__ == '__main__':
    main()
