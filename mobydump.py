#!/usr/bin/env python

"""
MobyDump downloads data from the MobyGames API for a specific platform, and outputs it to
a delimiter-separated value file or JSON.

https://github.com/unexpectedpanda/mobydump
"""
import html
import json
import os
import pathlib
import sys
from typing import Any

import pandas as pd
from dotenv import load_dotenv  # type: ignore

import modules.constants as const
from modules.data_sanitize import reorder_columns, restructure_mobygames_response, sanitize_columns
from modules.get_mg_data import add_games, get_game_details, get_games, get_platforms
from modules.input import user_input
from modules.requests import request_wait
from modules.utils import Font, eprint, old_windows

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

        # Set the request headers
        headers: dict[str, str] = {'Accept': 'application/json', 'User-Agent': user_agent}

        # ================================================================================
        # Get platforms if requested by the user
        # ================================================================================

        if args.platforms:
            platforms = get_platforms(api_key, headers)

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

            # Set the rate limit
            rate_limit: int = 10

            if os.getenv('MOBY_RATE'):
                rate_limit = int(os.getenv('MOBY_RATE'))  # type: ignore

            if args.ratelimit:
                rate_limit = args.ratelimit

            # Set the output file
            output_file: str = 'output.txt'

            if args.output:
                output_file = args.output

            # Set the output file type
            output_file_type: int = 1

            if args.filetype:
                output_file_type = args.filetype

            # Set the delimiter
            delimiter: str = '\t'

            if args.delimiter:
                delimiter = args.delimiter

                encoded_delimiter: str = bytearray(delimiter, encoding='utf-8').decode(
                    'unicode_escape'
                )

                # Deal with escaped characters like \t
                if delimiter.startswith('\\'):
                    delimiter = encoded_delimiter

                if len(encoded_delimiter) > 1:
                    eprint(
                        f'Delimiter is more than one byte long in unicode ({delimiter} = {delimiter.encode('utf-8')!r}). '
                        'Choose another character. Exiting...',
                        level='error',
                        indent=0,
                    )
                    sys.exit(1)

            # Get the platform name if we know it already
            platform_name: str = f'platform {platform_id!s}'

            if not pathlib.Path('cache/platforms.json').is_file():
                get_platforms()
                request_wait(rate_limit)

            with open(pathlib.Path('cache/platforms.json'), encoding='utf-8') as platform_cache:
                cached_platforms = json.load(platform_cache)

                for cached_platform in cached_platforms['platforms']:
                    if cached_platform['platform_id'] == platform_id:
                        platform_name = (
                            f'the {Font.b}{cached_platform["platform_name"]}{Font.be} platform'
                        )

            # Set up the cache folders
            pathlib.Path(f'cache/{platform_id}/games-platform').mkdir(parents=True, exist_ok=True)

            # Read the requests status file if it exists
            completion_status: dict[str, bool] = {
                'stage_1_finished': False,
                'stage_2_finished': False,
            }

            if pathlib.Path(f'cache/{platform_id}/status.json').is_file():
                with open(
                    pathlib.Path(f'cache/{platform_id}/status.json'), encoding='utf-8'
                ) as status_cache:
                    try:
                        completion_status = json.load(status_cache)
                    except Exception:
                        pass

            # Read the game cache file if it exists
            game_cache: dict[str, Any] = {}

            if pathlib.Path(f'cache/{platform_id}/games.json').is_file():
                with open(
                    pathlib.Path(f'cache/{platform_id}/games.json'), encoding='utf-8'
                ) as platform_request_cache:
                    try:
                        game_cache = json.load(platform_request_cache)
                    except Exception:
                        pass

            # Set up the games list for populating
            games_list: list[dict[str, Any]] = []

            # If everything has already been downloaded, ask the user if they want to redownload or write out from
            # cache.
            resume: str = ''

            if completion_status['stage_1_finished'] and completion_status['stage_2_finished']:
                while resume != 'r' and resume != 'w':
                    eprint(
                        f'\nThe {platform_name} platform has already been downloaded. Do you want to redownload (r), or write the file from cache (w)?',
                        level='warning',
                        indent=False,
                    )
                    resume = input('\n> ')
                    eprint('')

            if resume == 'r':
                # Delete the game cache file
                if pathlib.Path(f'cache/{platform_id}/games.json').is_file():
                    pathlib.Path(f'cache/{platform_id}/games.json').unlink()

                # Delete the game details files
                for game_details_file in pathlib.Path(f'cache/{platform_id}/games-platform/').glob(
                    '*.*'
                ):
                    game_details_file.unlink()

                # Rewrite the status file
                completion_status: dict[str, bool] = {
                    'stage_1_finished': False,
                    'stage_2_finished': False,
                }

                with open(
                    pathlib.Path(f'cache/{platform_id}/status.json'), 'w', encoding='utf-8'
                ) as status_cache:
                    status_cache.write(json.dumps(completion_status, indent=4))

                # Empty out the cache in memory
                game_cache = {}

            # Repopulate the games list if resuming or writing out from cache
            if not games_list:
                for values in game_cache.values():
                    games_list = add_games(values, games_list, args)

            # Stage 1: Download platform level details
            if not completion_status['stage_1_finished']:
                games_list = get_games(
                    game_cache,
                    games_list,
                    platform_id,
                    platform_name,
                    completion_status,
                    api_key,
                    rate_limit,
                    headers,
                    args,
                )

            # Stage 2: Download individual game details
            if not completion_status['stage_2_finished']:
                get_game_details(
                    games_list,
                    platform_id,
                    completion_status,
                    api_key,
                    rate_limit,
                    headers,
                )

            # Enrich the existing game list with individual game details
            for game in games_list:
                if pathlib.Path(
                    f'cache/{platform_id}/games-platform/{game['game_id']}.json'
                ).is_file():
                    with open(
                        pathlib.Path(f'cache/{platform_id}/games-platform/{game['game_id']}.json'),
                        encoding='utf-8',
                    ) as game_details_cache:
                        loaded_game_details: dict[str, Any] = json.load(game_details_cache)

                        # Set up keys to ignore
                        ignore_keys: list[str] = ['platform_id', 'platform_name']

                        # Add the remaining keys to the game
                        for key, values in loaded_game_details.items():
                            if key not in ignore_keys:
                                if not args.raw:
                                    # Rework data to be better suited to a database
                                    game = restructure_mobygames_response(game, 2, key, values)
                                else:
                                    game[key] = values

            # Write the output file
            eprint(
                f'\n{Font.success}Finished requesting all titles. Writing data to {Font.b}{output_file}{Font.be}...{Font.end}',
                indent=False,
            )

            if output_file_type == 1:
                # Create a Pandas dataframe from the JSON data to tabulate it easily
                df = pd.json_normalize(games_list)

                # Sanitize data in the columns
                df = sanitize_columns(df)

                # Reorder data
                if not args.raw:
                    df = reorder_columns(df)

                # Write to delimited file, using a BOM so Microsoft apps interpret the encoding correctly
                df.to_csv(output_file, index=False, encoding='utf-8-sig', sep=delimiter)

            elif output_file_type == 2:
                with open(output_file, 'w', encoding='utf-8-sig') as file:
                    file.write(json.dumps(games_list, indent=2))

            eprint(
                f'{Font.success}Finished requesting all titles. Writing data to {Font.b}{output_file}{Font.be}... done.{Font.end}',
                overwrite=True,
                wrap=False,
            )

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
