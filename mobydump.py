#!/usr/bin/env python

"""
Downloads data from MobyGames and outputs it in a format suitable to import into
Microsoft Access.

https://github.com/unexpectedpanda/mobydump
"""

import argparse
import html
import os
import pandas as pd
import requests
import sys

from dotenv import load_dotenv
from time import sleep
from typing import Any

from modules.utils import eprint, Font, SmartFormatter

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

    #  Set up ArgParse
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

    headers: dict[str, str] = {'Accept': 'application/json'}

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

    # Get the platforms
    if args.platforms:
        # Retrieve the platforms
        eprint('Retrieving platforms...')

        url: str = f'https://api.mobygames.com/v1/platforms?api_key={html.escape(os.getenv('MOBY_API'))}'

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
            while True:
                offset_increment: int = 100

                eprint(f'Downloading titles {offset}-{offset+offset_increment}...', overwrite=True)

                url: str = f'https://api.mobygames.com/v1/games?api_key={os.getenv('MOBY_API')}&platform={platform}&offset={offset}&limit={offset_increment}'

                # Increment the offset
                offset = offset + offset_increment

                games = requests.get(url, headers=headers)
                games.raise_for_status()

                games=games.json()

                # Break the loop if MobyGames returns an empty response, as we've reached the end
                if not games['games']:
                    eprint(f'Finished downloading all titles.', overwrite=True)
                    break
                else:
                    eprint(f'Downloading titles {offset-offset_increment}-{offset}... done.', overwrite=True)

                add_games(games)

                eprint(f'Waiting {rate_limit} seconds...')
                sleep(rate_limit)
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

        # Create a Pandas dataframe from the JSON data
        df = pd.json_normalize(game_list)

        # Clear out newlines
        df = df.replace(r'\n',' ', regex=True)

        # Write to delimited file
        df.to_csv(output_file, index=False, encoding='utf-8', sep=delimiter)

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
