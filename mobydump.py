#!/usr/bin/env python

"""
Downloads data from MobyGames and outputs it in a format suitable to import into
Microsoft Access.

https://github.com/unexpectedpanda/mobydump
"""

import html
import json
import os
import pandas as pd
import requests
import sys

from dotenv import load_dotenv
from time import sleep
from typing import Any

from modules.input import user_input
from modules.utils import eprint, Font

__version__: int = 0.01

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
    eprint(f'  /_/ MOBYDUMP {__version__}\n', wrap=False)

    # Get user input
    args = user_input()

    # Set API request details
    headers: dict[str, str] = {'Accept': 'application/json'}
    api_key: str = html.escape(os.getenv('MOBY_API'))

    # Get the platforms if requested by the user
    if args.platforms:
        # Retrieve the platforms
        eprint('Retrieving platforms...')

        url: str = f'https://api.mobygames.com/v1/platforms?api_key={api_key}'

        platforms: dict[list[dict, str|int]] = requests.get(url, headers=headers).json()

        # Sort the response by name
        platform_list: list[str|int] = sorted(platforms['platforms'], key=lambda d: d['platform_name'])

        # Get the longest platform name length for column formatting
        platform_width: int = max([len(x['platform_name']) for x in platforms['platforms']])

        # Print the platforms
        eprint('Retrieving platforms... done.', overwrite=True)
        eprint(f'\n{Font.b}{Font.u}{"NAME":<{platform_width+4}}{"ID":>5}{Font.end}\n')
        for platform in platform_list:
            eprint(f'{platform["platform_name"]:<{platform_width+4}}{platform["platform_id"]:>5}', wrap=False)

        sys.exit(0)

    # Get the games if requested by the user
    if args.games:
        # Set the platform
        platform: int = args.games

        # Set the offset
        offset: int = 0

        if args.startfrom:
            offset = args.startfrom

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

        # Retrieve the games for the platform
        eprint(f'Retrieving games from platform {platform} and outputting to {Font.b}{output_file}{Font.be}...\n\n')

        game_list: list[dict, str|int] = []

        def add_games(games):
            # Move the title to first in the list
            for values in games.values():
                for value in values:
                    value = {'title': value.pop('title'), **value}

                    # Format alternate titles field
                    if 'alternate_titles' in value:
                        alternate_titles: list[str] = []

                        for alternate_title in value['alternate_titles']:
                            alternate_titles.append(f'{alternate_title["description"]}: {alternate_title["title"]}')

                        if alternate_titles:
                            value['alternate_titles'] = ', '.join(alternate_titles)
                        else:
                            value['alternate_titles'] = ''

                    # Format genre field
                    if 'genres' in value:
                        genres: list[str] = []

                        for genre in value['genres']:
                            if 'genre_name' in genre:
                                genres.append(f'{genre["genre_category"]}: {genre["genre_name"]}')

                        if genres:
                            value['genres'] = ', '.join(genres)
                        else:
                            value['genres'] = ''

                    # Format platforms field
                    if 'platforms' in value:
                        game_platforms: list[str] = []

                        for platforms in value['platforms']:
                            game_platforms.append(f'{platforms["platform_name"]} ({platforms["first_release_date"]})')

                        if platforms:
                            value['platforms'] = ', '.join(game_platforms)
                        else:
                            value['platforms'] = ''

                    game_list.append(value)

        try:
            i: int = 0

            while True:
                offset_increment: int = 100

                # Wait for the rate limit after the first request
                if i > 0:
                    for j in range(rate_limit):
                        eprint(f'• Waiting {rate_limit-j} seconds until next request...', overwrite=True)
                        sleep(1)
                else:
                    i = i + 1

                eprint(f'• Requesting titles {offset}-{offset+offset_increment}...', overwrite=True)

                url: str = f'https://api.mobygames.com/v1/games?api_key={api_key}&platform={platform}&offset={offset}&limit={offset_increment}'

                # Increment the offset
                offset = offset + offset_increment

                games = requests.get(url, headers=headers)
                games.raise_for_status()

                games=games.json()

                # Break the loop if MobyGames returns an empty response, as we've reached the end
                if not games['games']:
                    eprint(f'\nFinished requesting all titles.', overwrite=True)
                    break
                else:
                    eprint(f'• Requesting titles {offset-offset_increment}-{offset}... done.\n', overwrite=True)

                add_games(games)
        except requests.exceptions.Timeout:
            eprint('Timeout, trying again in x seconds')
            sys.exit(1)
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 401:
                eprint('Unauthorized access. Have you provided a MobyGames API key?')
                eprint(err)
                sys.exit(1)
            if err.response.status_code == 422:
                eprint('The parameter sent was the right type, but was invalid')
                eprint(err)
                sys.exit(1)
            if err.response.status_code == 429:
                eprint('Too many requests, trying again in x seconds')
                eprint(err)
                sys.exit(1)
            else:
                eprint(err)
                sys.exit(1)


        # Sort the list by title
        game_list = sorted(game_list, key=lambda d: d['title'])

        # Write the output file
        if output_file_type == 1:
            # Create a Pandas dataframe from the JSON data
            df = pd.json_normalize(game_list)

            # Clear out new lines
            df = df.replace(r'\n',' ', regex=True)

            # Write to delimited file
            df.to_csv(output_file, index=False, encoding='utf-8', sep=delimiter)
        elif output_file_type == 2:
            with open(output_file, 'w', encoding='utf-8') as file:
                file.write(json.dumps(game_list, indent=2))

else:
    eprint(
        '\nMobyDump needs a MobyGames API key to contine. To add one:'
        f'\n\n1. Create a file named {Font.b}.env{Font.be} in the same folder MobyDump is '
        'in.'
        '\n2. Add your MobyGames API key as follows, replacing '
        '\n   <MOBYGAMES_API_KEY> with your API key:'
        '\n\nMOBY_API="<MOBYGAMES_API_KEY>"'
        '\n\nExiting...', level='error', indent=0, wrap=False)

    sys.exit(1)
