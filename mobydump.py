#!/usr/bin/env python

"""
Downloads data from Moby Games and outputs it in a format suitable to import into
Microsoft Access.

https://github.com/unexpectedpanda/mobydump

You must set the MOBY_API environment variable to your Moby Games API key for this to
work.

To set the environment variable permanently in Windows 10:

1. Run sysdm.cpl.
2. Click the **Advanced** tab.
3. Click **Environment variables**.
4. In the **User variables** section, click **New**.
5. Set the **Variable name** to MOBYAPI, and the **Variable value** to your API key.
6. Click **OK**, then click **OK* again.
7. Close and reopen any terminal windows you have open so the environment variable
   takes effect. If you're using the Visual Studio Code terminal, the whole app needs
   to be restarted.
8. Type echo %MOBY_API% to check that your Moby Games API key is echoed back to you.
"""

import argparse
import os
import pandas as pd
import requests
import sys

from modules.utils import eprint, Font, SmartFormatter

__version__: int = 0.01

if 'MOBY_API' in os.environ:
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
    eprint(f'  /_/ MOBY DUMP {__version__}\n', wrap=False)

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        allow_abbrev=False,
        formatter_class=SmartFormatter,
        add_help=False,
    )

    parser.add_argument(
        '-h', '--help', '-?', action='help', default=argparse.SUPPRESS, help=argparse.SUPPRESS
    )

    parser.add_argument(
        '-p', '--platforms',
        action='store_true',
        help='R|Get the platforms and their IDs from Moby Games.'
        '\n\n',
    )

    parser.add_argument(
        '-g', '--games',
        metavar='<PLATFORM_ID>',
        type=int,
        help='R|Get all game details from Moby Games that belong'
        '\nto a specific platform ID.'
        '\n\n',
    )

    parser.add_argument(
        '-o', '--output',
        metavar='"<FILENAME>"',
        type=str,
        help=f'R|The filename to output to. Defaults to {Font.b}output.txt{Font.be}.'
        '\nMust be used with --games.'
        '\n\n',
    )

    parser.add_argument(
        '-d', '--delimiter',
        metavar='"<DELIMITER>"',
        type=str,
        help=f'R|The delimiter to use in the output file. Defaults'
        f'\nto {Font.b}tab{Font.be}. Must be used with --games.'
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

    # Get the platforms
    if args.platforms:
        # Retrieve the platforms
        eprint('Retrieving platforms...\n')

        url: str = f'https://api.mobygames.com/v1/platforms?api_key={os.environ['MOBY_API']}'
        platforms: dict[list[dict, str|int]] = requests.get(url, headers=headers).json()

        # Sort the response by name
        platform_list: list[str|int] = sorted(platforms['platforms'], key=lambda d: d['platform_name'])

        # Get the longest platform name length for column formatting
        platform_width: int = max([len(x['platform_name']) for x in platforms['platforms']])

        # Print the platforms
        eprint(f'\n{Font.b}{Font.u}{"NAME":<{platform_width+4}}{"ID":>5}{Font.end}\n')
        for platform in platform_list:
            eprint(f'{platform["platform_name"]:<{platform_width+4}}{platform["platform_id"]:>5}', wrap=False)

        sys.exit(0)

    if args.games:
        platform: int = args.games

        # Set the output file
        output_file: str = 'output.txt'

        if args.output:
            output_file = args.output

        # Set the delimiter
        delimiter: str = '\t'

        if args.delimiter:
            delimiter = args.delimiter

        # Retrieve the games for the platform
        eprint(f'Retrieving games from platform {platform} and outputting to {Font.b}{output_file}{Font.be}...\n')

        url: str = f'https://api.mobygames.com/v1/games?api_key={os.environ['MOBY_API']}&platform={platform}'

        games = requests.get(url, headers=headers).json()

        # Move the title to first in the list
        game_list: list[dict, str|int] = []

        for key, values, in games.items():
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
        '\nAPI key missing. Set the MOBI_API environment variable to your Moby Games'
        '\nAPI key to continue. Exiting...', level='error')
    sys.exit(1)
