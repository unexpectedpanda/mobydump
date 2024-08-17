#!/usr/bin/env python

"""
Downloads data from MobyGames and outputs it to a delimiter-separated value file or JSON.

https://github.com/unexpectedpanda/mobydump
"""
from __future__ import annotations

import html
import json
import os
import sys
from time import sleep
from typing import TYPE_CHECKING, Any

import pandas as pd
from dotenv import load_dotenv  # type: ignore

import modules.constants as const
from modules.api_requests import mobygames_request
from modules.data_sanitize import reorder_columns, sanitize_columns, sanitize_mobygames_response
from modules.input import user_input
from modules.utils import Font, eprint

if TYPE_CHECKING:
    import requests

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

    # Get the platforms if requested by the user
    if args.platforms:
        # Make the request for the platforms
        eprint('Retrieving platforms...')

        platforms: dict[str, list[dict[str, str | int]]] = mobygames_request(
            f'https://api.mobygames.com/v1/platforms?api_key={api_key}'
        ).json()

        # Sort the response by name
        platform_list: list[dict[str, str | int]] = sorted(
            platforms['platforms'], key=lambda d: d['platform_name']
        )

        input(platforms['platforms'])
        input(platform_list)

        # Get the longest platform name length for column formatting
        platform_width: int = max([len(str(x['platform_name'])) for x in platforms['platforms']])

        # Print the platforms
        eprint('Retrieving platforms... done.', overwrite=True)
        eprint(f'\n{Font.b}{Font.u}{"NAME":<{platform_width+4}}{"ID":>5}{Font.end}\n')
        for platform in platform_list:
            eprint(
                f'{platform["platform_name"]:<{platform_width+4}}{platform["platform_id"]!s:>5}',
                wrap=False,
            )

        sys.exit(0)

    # Get the games if requested by the user
    if args.games:
        # Set the platform
        platform_id: int = args.games

        #! TODO: Resume
        # Set the offset
        offset: int = 0

        if args.restart:
            offset = 0

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

        # Retrieve the games for the specified platform
        eprint(
            f'Retrieving games from platform {platform_id} and outputting to {Font.b}{output_file}{Font.be}...\n\n'
        )

        game_list: list[dict[str, Any]] = []

        def add_games(games_dict: dict[str, Any]) -> None:
            """
            Reworks game data to be suitable for databases, then adds the game to a list.

            Args:
                games_dict (dict[str, Any]): A response from the MobyGames API containing game details.
            """
            for games_values in games_dict.values():
                for game in games_values:
                    # Rework data to be better suited to a database
                    if not args.raw:
                        game = sanitize_mobygames_response(game)

                    game_list.append(game)

        # Get all the response pages for a platform, and add the games to a list
        i: int = 0

        while True:
            offset_increment: int = 100

            # Wait for the rate limit after the first request
            if i > 0:
                for j in range(rate_limit):
                    eprint(
                        f'• Waiting {rate_limit-j} seconds until next request...', overwrite=True
                    )
                    sleep(1)
            else:
                i = i + 1

            eprint(f'• Requesting titles {offset}-{offset+offset_increment}...', overwrite=True)

            # Make the request
            games: requests.models.Response = mobygames_request(
                f'https://api.mobygames.com/v1/games?api_key={api_key}&platform={platform_id}&offset={offset}&limit={offset_increment}'
            )

            games.raise_for_status()

            games_dict: dict[str, Any] = games.json()

            # Increment the offset
            offset = offset + offset_increment

            add_games(games_dict)

            # Break the loop if MobyGames returns an empty response or if there's less than 100 titles, as we've
            # reached the end
            if 'games' in games_dict:
                eprint(
                    f'• Requesting titles {offset-offset_increment}-{offset}... done.\n',
                    overwrite=True,
                )

                if len(games_dict['games']) < 100:
                    eprint('Finished requesting all titles.')
                    break

            elif not games_dict['games']:
                eprint('\nFinished requesting all titles.', overwrite=True)
                break

        # Sort the game list by title
        game_list = sorted(game_list, key=lambda d: d['title'])

        # Write the output file
        if output_file_type == 1:
            # Create a Pandas dataframe from the JSON data to tabulate it easily
            df = pd.json_normalize(game_list)

            # Sanitize data in the columns
            df = sanitize_columns(df)

            # Reorder data
            if not args.raw:
                df = reorder_columns(df)

            # Write to delimited file
            df.to_csv(output_file, index=False, encoding='utf-8', sep=delimiter)

        elif output_file_type == 2:
            with open(output_file, 'w', encoding='utf-8') as file:
                file.write(json.dumps(game_list, indent=2))

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
