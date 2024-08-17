#!/usr/bin/env python

"""
Downloads data from MobyGames and outputs it to a delimiter-separated value file or JSON.

https://github.com/unexpectedpanda/mobydump
"""

import html
import json
import numpy as np
import os
import pandas as pd
import requests
import sys

from dotenv import load_dotenv
from time import sleep

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

            encoded_delimiter: bytes = bytearray(delimiter, encoding='utf-8').decode('unicode_escape')

            # Deal with escaped characters like \t
            if delimiter.startswith('\\'):
                delimiter = encoded_delimiter

            if len(encoded_delimiter) > 1:
                eprint(
                    f'Delimiter is more than one byte long in unicode ({delimiter} = {delimiter.encode('utf-8')}). '
                    'Choose another character. Exiting...', level='error', indent=0)
                sys.exit(1)

        # Retrieve the games for the platform
        eprint(f'Retrieving games from platform {platform} and outputting to {Font.b}{output_file}{Font.be}...\n\n')

        game_list: list[dict, str|int] = []

        def add_games(games):
            # Rework data to be better suited to a database
            for games_values in games.values():
                for game in games_values:
                    if not args.raw:
                        # Format alternate titles field
                        if 'alternate_titles' in game:
                            alternate_titles: list[str] = []

                            for alternate_title in game['alternate_titles']:
                                alternate_titles.append(f'{alternate_title["description"]}: {alternate_title["title"]}')

                            if alternate_titles:
                                game['alternate_titles'] = ', '.join(alternate_titles)
                            else:
                                game['alternate_titles'] = ''

                        # Format genre field
                        if 'genres' in game:
                            if game['genres']:
                                for genre in game['genres']:
                                    game[f'genres ({genre["genre_category"]})'] = genre["genre_name"]

                            del(game['genres'])

                        # Format platforms field
                        if 'platforms' in game:
                            if game['platforms']:
                                game_platforms: list[str] = []

                                for platforms in game['platforms']:
                                    game_platforms.append(f'{platforms["platform_name"]} ({platforms["first_release_date"]})')

                                if platforms:
                                    game['platforms'] = ', '.join(game_platforms)
                                else:
                                    game['platforms'] = ''

                        # Format images
                        if 'sample_cover' in game:
                            if game['sample_cover']:
                                if 'platforms' in game['sample_cover']:
                                    game['sample_cover']['platforms'] = game['sample_cover']['platforms'][0]

                                for key in game['sample_cover']:
                                    game[f'Sample cover {str(key).replace("_", " ")}'] = game['sample_cover'][key]

                            del(game['sample_cover'])

                        if 'sample_screenshots' in game:
                            if game['sample_screenshots']:
                                for i, screenshot in enumerate(game['sample_screenshots'], start=1):
                                    for key, value in screenshot.items():
                                        game[f'Screenshot {i} {key}'] = value

                            del[game['sample_screenshots']]

                    game_list.append(game)

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

                add_games(games)

                # Break the loop if MobyGames returns an empty response or if there's less than 100 titles, as we've
                # reached the end
                if 'games' in games:
                    eprint(f'• Requesting titles {offset-offset_increment}-{offset}... done.\n', overwrite=True)

                    if len(games['games']) < 100:
                        eprint(f'Finished requesting all titles.')
                        break

                elif not games['games']:
                    eprint(f'\nFinished requesting all titles.', overwrite=True)
                    break


        except requests.exceptions.Timeout:
            eprint('Timeout, trying again in x seconds')
            sys.exit(1)
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 401:
                eprint('Unauthorized access. Have you provided a MobyGames API key?')
                eprint(f'\n{err}')
                sys.exit(1)
            if err.response.status_code == 422:
                eprint('The parameter sent was the right type, but was invalid.')
                eprint(f'\n{err}')
                sys.exit(1)
            if err.response.status_code == 429:
                eprint('Too many requests, trying again in x seconds...')
                eprint(f'\n{err}')
                sys.exit(1)
            if err.response.status_code == 504:
                eprint('Gateway timeout for URL, trying again in x seconds...')
                eprint(f'\n{err}')
                sys.exit(1)
            else:
                eprint(f'\n{err}')
                sys.exit(1)


        # Sort the list by title
        game_list = sorted(game_list, key=lambda d: d['title'])

        # Write the output file
        if output_file_type == 1:
            # Create a Pandas dataframe from the JSON data to tabulate it easily
            df = pd.json_normalize(game_list)

            # Clear out new lines from data
            df = df.replace(r'\n', ' ', regex=True)

            # Clear out tabs from data
            df = df.replace(r'\t', '    ', regex=True)

            # Normalize curly quotes and replace other problem characters
            df = df.replace(['“', '”'], '"', regex=True).replace(['‘', '’'], '\'', regex=True).replace(['\u200b', '\u200c'], '', regex=True)

            # Remove null values
            df = df.replace([None, np.nan],'')

            # Reorder data
            if not args.raw:
                def reorder_columns(new_position: int, new_name: str, original_name:str) -> int:
                    try:
                        df.insert(new_position, new_name, df.pop(original_name))
                    except:
                        pass

                    return new_position + 1

                column_number: int = 0

                column_number = reorder_columns(column_number, 'Title', 'title')
                column_number = reorder_columns(column_number, 'Alternative titles', 'alternate_titles')
                column_number = reorder_columns(column_number, 'Game ID', 'game_id')
                column_number = reorder_columns(column_number, 'MobyGames URL', 'moby_url')
                column_number = reorder_columns(column_number, 'Platforms and release dates', 'platforms')
                column_number = reorder_columns(column_number, 'Description', 'description')
                column_number = reorder_columns(column_number, 'Official URL', 'official_url')
                column_number = reorder_columns(column_number, 'MobyGames score', 'moby_score')
                column_number = reorder_columns(column_number, 'Number of voters', 'num_votes')
                column_number = reorder_columns(column_number, 'Genres (Basic)', 'genres (Basic Genres)')
                column_number = reorder_columns(column_number, 'Genres (Perspective)', 'genres (Perspective)')
                column_number = reorder_columns(column_number, 'Genres (Setting)', 'genres (Setting)')

                # Add the remaining genre columns
                genre_columns: list[str] = []

                for column in df.columns:
                    if column.startswith('genre'):
                        genre_columns.append(column)

                genre_columns.sort(reverse=True)

                for column in genre_columns:
                    column_number = reorder_columns(column_number, column.replace('genres', 'Genres'), column)

                # Add sample cover details
                column_number = reorder_columns(column_number, 'Sample cover image', 'Sample cover image')
                column_number = reorder_columns(column_number, 'Sample cover width', 'Sample cover width')
                column_number = reorder_columns(column_number, 'Sample cover height', 'Sample cover height')
                column_number = reorder_columns(column_number, 'Sample cover platforms', 'Sample cover platforms')
                column_number = reorder_columns(column_number, 'Sample cover thumbnail image', 'Sample cover thumbnail image')
                column_number = reorder_columns(column_number, 'Sample screenshots', 'Sample screenshots')

                # Add screenshots
                screenshot_columns: list[str] = []

                for column in df.columns:
                    if column.startswith('Screenshot'):
                        screenshot_columns.append(column)

                highest_screenshot_number: int = max([int(''.join(filter(str.isdigit, x))) for x in screenshot_columns])

                for i in range(1, highest_screenshot_number + 1):
                    column_number = reorder_columns(column_number, f'Screenshot {i} image', f'Screenshot {i} image')
                    column_number = reorder_columns(column_number, f'Screenshot {i} width', f'Screenshot {i} width')
                    column_number = reorder_columns(column_number, f'Screenshot {i} height', f'Screenshot {i} height')
                    column_number = reorder_columns(column_number, f'Screenshot {i} caption', f'Screenshot {i} caption')
                    column_number = reorder_columns(column_number, f'Screenshot {i} thumbnail image', f'Screenshot {i} thumbnail_image')

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
