#!/usr/bin/env python

"""
Downloads data from MobyGames and outputs it to a delimiter-separated value file or JSON.

https://github.com/unexpectedpanda/mobydump
"""
from __future__ import annotations

import html
import json
import os
import pathlib
import sys
from copy import deepcopy
from time import sleep
from typing import Any

import pandas as pd
from dotenv import load_dotenv  # type: ignore

import modules.constants as const
from modules.api_requests import mobygames_request
from modules.data_sanitize import reorder_columns, sanitize_columns, sanitize_mobygames_response
from modules.input import user_input
from modules.utils import Font, eprint

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

    # ====================================================================================
    # Get platforms if requested by the user
    # ====================================================================================
    def get_platforms() -> dict[str, list[dict[str, str | int]]]:
        """
        Make the platform request, and write the results to a JSON file for an offline
        cache.

        Returns:
            dict[str, list[dict[str, str | int]]]: The contents of the response, in JSON form.
        """
        platforms: dict[str, list[dict[str, str | int]]] = mobygames_request(
            f'https://api.mobygames.com/v1/platforms?api_key={api_key}', '• Retrieving platforms...'
        ).json()

        eprint('• Retrieving platforms... done.', overwrite=True)

        # Store the response in a file
        if not pathlib.Path('cache').is_dir():
            pathlib.Path('cache').mkdir(parents=True, exist_ok=True)

        with open(pathlib.Path('cache/platforms.json'), 'w', encoding='utf-8') as platform_cache:
            platform_cache.write(json.dumps(platforms, indent=4))

        return platforms

    if args.platforms:
        platforms = get_platforms()

        # Sort the response by name
        platform_list: list[dict[str, str | int]] = sorted(
            platforms['platforms'], key=lambda d: d['platform_name']
        )

        # Get the longest platform name length for column formatting
        platform_width: int = max([len(str(x['platform_name'])) for x in platforms['platforms']])

        # Print the platforms
        eprint(f'\n{Font.b}{Font.u}{"NAME":<{platform_width+4}}{"ID":>5}{Font.end}\n')
        for platform in platform_list:
            eprint(
                f'{platform["platform_name"]:<{platform_width+4}}{platform["platform_id"]!s:>5}',
                wrap=False,
            )

        sys.exit(0)

    # ====================================================================================
    # Get games if requested by the user
    # ====================================================================================
    if args.games:
        # Set the platform
        platform_id: int = args.games

        # Set the rate limit
        rate_limit: int = 10

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

            encoded_delimiter: str = bytearray(delimiter, encoding='utf-8').decode('unicode_escape')

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
            eprint(f'• Waiting {rate_limit} seconds until next request...')

            for j in range(rate_limit):
                eprint(f'• Waiting {rate_limit-j} seconds until next request...', overwrite=True)
                sleep(1)

            # Delete the previous line printed to screen
            eprint('\033M\033[2K\033M')

        with open(pathlib.Path('cache/platforms.json'), encoding='utf-8') as platform_cache:
            cached_platforms = json.load(platform_cache)

            for cached_platform in cached_platforms['platforms']:
                if cached_platform['platform_id'] == platform_id:
                    platform_name = (
                        f'the {Font.b}{cached_platform["platform_name"]}{Font.be} platform'
                    )

        # Retrieve the games for the specified platform
        eprint(f'• Retrieving games from {platform_name}.')

        games_list: list[dict[str, Any]] = []

        def add_games(games_dict: dict[str, Any]) -> None:
            """
            Reworks game data to be suitable for databases, then adds the game to a list.

            Args:
                games_dict (dict[str, Any]): A response from the MobyGames API containing game details.
            """
            for game_values in games_dict.values():
                for game_value in game_values:
                    # Rework data to be better suited to a database
                    if not args.raw:
                        game_value = sanitize_mobygames_response(deepcopy(game_value))

                    games_list.append(game_value)

        # Read the platform contents cache file if it exists
        platform_contents_cache: dict[str, Any] = {'finished': False}

        if pathlib.Path(f'cache/{platform_id}.json').is_file():
            with open(
                pathlib.Path(f'cache/{platform_id}.json'), encoding='utf-8'
            ) as platform_request_cache:
                try:
                    platform_contents_cache = json.load(platform_request_cache)
                except Exception:
                    pass

        # Set the request offset
        offset: int = 0
        offset_increment: int = 100

        # Change the offset if we need to resume
        if len(platform_contents_cache) > 1 and not platform_contents_cache['finished']:
            # Get the last key in the cache, and set the offset appropriately
            offset = int(list(platform_contents_cache)[-1]) + offset_increment

            eprint(f'• Request was previously interrupted, resuming from offset {offset}')

        # Get all the response pages for a platform, and add the games to a list
        i: int = 0

        while True:
            # Wait for the rate limit after the first request
            if i > 0:
                for j in range(rate_limit):
                    eprint(
                        f'• Waiting {rate_limit-j} seconds until next request...', overwrite=True
                    )
                    sleep(1)

                # Delete the previous line printed to screen
                eprint('\033M\033[2K\033M')
            else:
                i += 1

            # If there's a cache file and we need to resume, do so. Otherwise, ask the user if they want to redownload
            # or write out from cache.
            redownload: str = ''

            if platform_contents_cache['finished']:
                while redownload != 'r' and redownload != 'w':
                    eprint(
                        f'\nThe {platform_name} platform has already been downloaded. Do you want to redownload (r), or write the file from cache (w)?',
                        level='warning',
                        indent=False,
                    )
                    redownload = input('\n> ')
                    eprint('')

            # User redownloads, or MobyDump auto-resumes because the request was previously marked as unfinished
            if not platform_contents_cache['finished'] or redownload == 'r':
                if redownload == 'r':
                    # Delete the cache file and empty out platform_contents_cache
                    pathlib.Path(f'cache/{platform_id}.json').unlink()
                    platform_contents_cache = {'finished': False}

                # Repopulate the games list if resuming
                if not platform_contents_cache['finished']:
                    for key, values in platform_contents_cache.items():
                        if key != 'finished':
                            add_games(values)

                # Make the request for the platform's games
                games: dict[str, Any] = mobygames_request(
                    f'https://api.mobygames.com/v1/games?api_key={api_key}&platform={platform_id}&offset={offset}&limit={offset_increment}',
                    f'• Requesting titles {offset}-{offset+offset_increment}...',
                ).json()

                # Add games to the cache, and then process them
                if 'games' in games:
                    if games['games']:
                        platform_contents_cache[str(offset)] = games

                add_games(games)

                # Increment the offset
                offset = offset + offset_increment

                # Break the loop if MobyGames returns an empty response or if there's less than 100 titles, as we've
                # reached the end
                end_loop: bool = False
                success_message: str = (
                    f'{Font.success}Finished requesting all titles. Writing data to {Font.b}{output_file}{Font.be}...{Font.end}'
                )

                if 'games' in games:
                    eprint(
                        f'• Requesting titles {offset-offset_increment}-{offset}... done.\n',
                        overwrite=True,
                    )

                    if len(games['games']) < 100:
                        eprint(success_message, wrap=False)
                        platform_contents_cache['finished'] = True
                        end_loop = True

                elif not games['games']:
                    eprint(f'\n{success_message}', wrap=False, overwrite=True)
                    platform_contents_cache['finished'] = True
                    end_loop = True
            # If the user chooses to write the file from cache, process the games from there
            elif redownload == 'w':
                eprint('')
                end_loop = True
                for key, values in platform_contents_cache.items():
                    if key != 'finished':
                        add_games(values)

            # Write the cache
            with open(
                pathlib.Path(f'cache/{platform_id}.json'), 'w', encoding='utf-8'
            ) as platform_request_cache:
                platform_request_cache.write(json.dumps(platform_contents_cache, indent=4))

            # End the loop if needed
            if end_loop:
                break

        # Sort the game list by title
        games_list = sorted(games_list, key=lambda d: d['title'])

        # Write the output file
        if output_file_type == 1:
            # Create a Pandas dataframe from the JSON data to tabulate it easily
            df = pd.json_normalize(games_list)

            # Sanitize data in the columns
            df = sanitize_columns(df)

            # Reorder data
            if not args.raw:
                df = reorder_columns(df)

            # Write to delimited file
            df.to_csv(output_file, index=False, encoding='utf-8', sep=delimiter)

        elif output_file_type == 2:
            with open(output_file, 'w', encoding='utf-8') as file:
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
