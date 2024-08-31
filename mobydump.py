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

import numpy as np
import pandas as pd
from dotenv import load_dotenv  # type: ignore

import modules.constants as const
from modules.data_sanitize import sanitize_dataframes
from modules.get_mg_data import get_game_details, get_game_ids_and_titles, get_games, get_platforms
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

            # Set the output file type
            output_file_type: int = 1

            if args.filetype:
                output_file_type = args.filetype

            # Set the prefix
            prefix: str = ''

            if args.prefix:
                prefix = args.prefix

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
                        f'Delimiter is more than one byte long in unicode ({delimiter} = '
                        f'{delimiter.encode('utf-8')!r}). Choose another character. Exiting...',
                        level='error',
                        indent=0,
                    )
                    sys.exit(1)

            # Get the platform name if we know it already
            platform_name: str = f'platform {platform_id!s}'
            raw_platform_name: str = ''

            if not pathlib.Path('cache/platforms.json').is_file():
                get_platforms(api_key, headers)
                request_wait(rate_limit)

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

            # If everything has already been downloaded, ask the user if they want to redownload or write out from
            # cache.
            resume: str = ''

            if completion_status['stage_1_finished'] and completion_status['stage_2_finished']:
                while resume != 'r' and resume != 'w':
                    eprint(
                        f'\nGames from {platform_name} have already been downloaded. Do you want to redownload (r), or '
                        'write new output files from cache (w)?',
                        level='warning',
                        indent=False,
                    )
                    resume = input('\n> ')
                    eprint('')

            if resume == 'r':
                # Delete the game cache file
                for game_file in pathlib.Path(f'cache/{platform_id}/games/').glob('*.json'):
                    game_file.unlink()

                # Delete the game details files
                for game_details_file in pathlib.Path(f'cache/{platform_id}/games-details/').glob(
                    '*.json'
                ):
                    game_details_file.unlink()

                # Rewrite the status file
                completion_status = {
                    'stage_1_finished': False,
                    'stage_2_finished': False,
                }

                with open(
                    pathlib.Path(f'cache/{platform_id}/status.json'), 'w', encoding='utf-8'
                ) as status_cache:
                    status_cache.write(json.dumps(completion_status, indent=4))

            # Stage 1: Download games for the platform
            if not completion_status['stage_1_finished']:
                get_games(
                    platform_id,
                    platform_name,
                    completion_status,
                    api_key,
                    rate_limit,
                    headers,
                )

            # Stage 2: Download individual game details
            if not completion_status['stage_2_finished']:
                get_game_details(
                    platform_id,
                    completion_status,
                    api_key,
                    rate_limit,
                    headers,
                )

            if output_file_type == 2:
                # Write the output file in JSON
                eprint(
                    f'\n{Font.success}Finished processing titles. Writing output file...'
                    f'{Font.end}',
                    indent=False,
                )

                # Enrich games with individual game details, and write to the JSON file
                for game_file in pathlib.Path(f'cache/{platform_id}/games/').glob('*.json'):
                    with open(pathlib.Path(game_file), encoding='utf-8') as platform_request_cache:
                        cache: dict[str, Any] = json.loads(platform_request_cache.read())

                        output_file: str = f'{prefix}{raw_platform_name}.json'

                        # Open the output JSON file and write the header
                        with open(pathlib.Path(output_file), 'w', encoding='utf-8-sig') as file:
                            file.write('{\n  "games": [\n')

                        # Add the game contents to the file
                        for i, game in enumerate(cache['games']):

                            if pathlib.Path(
                                f'cache/{platform_id}/games-details/{game['game_id']}.json'
                            ).is_file():
                                with open(
                                    pathlib.Path(
                                        f'cache/{platform_id}/games-details/{game['game_id']}.json'
                                    ),
                                    encoding='utf-8',
                                ) as game_details_cache:
                                    loaded_game_details: dict[str, Any] = json.load(
                                        game_details_cache
                                    )

                                    # Add the game details keys to the game
                                    for key, values in loaded_game_details.items():
                                        game[key] = values

                                    # Sort by alphabetically by key
                                    game = dict(sorted(game.items()))

                                    # Move game ID and title to the top
                                    game = {'game_id': game.pop('game_id'), **game}
                                    game = {'title': game.pop('title'), **game}

                                    with open(
                                        pathlib.Path(output_file), 'a', encoding='utf-8-sig'
                                    ) as file:
                                        game_json: str = json.dumps(game, indent=2)

                                        if i + 1 < len(cache['games']):
                                            game_json = f'{game_json},'

                                        for line in game_json.split('\n'):
                                            file.write(f'    {line}\n')

                        # Close the file
                        with open(pathlib.Path(output_file), 'a', encoding='utf-8-sig') as file:
                            file.write('  ]\n}\n')

                eprint(
                    f'{Font.success}Finished processing titles. Writing output file... '
                    f'done.{Font.end}',
                    overwrite=True,
                    wrap=False,
                )

            elif output_file_type == 1:
                # Organize the data into separate tables for output, as Access can't
                # handle more than 255 columns of data, and the API returns data of
                # different shapes
                eprint(
                    '• Organizing game data...',
                    indent=False,
                )

                game_ids: list[int] = []
                games_dataframe: pd.DataFrame = pd.DataFrame()

                for game_file in pathlib.Path(f'cache/{platform_id}/games/').glob('*.json'):
                    with open(pathlib.Path(game_file), encoding='utf-8') as platform_request_cache:
                        cache = json.loads(platform_request_cache.read())

                        game_ids.extend([x[0] for x in get_game_ids_and_titles(cache)])
                        temp_games_data_frame = pd.json_normalize(
                            data=cache, record_path='games', errors='ignore'
                        )

                        # Remove null values so there aren't datatype concat problems
                        temp_games_data_frame = temp_games_data_frame.replace([None, np.nan], '')

                        if games_dataframe.empty:
                            games_dataframe = temp_games_data_frame.copy(deep=True)
                        else:
                            games_dataframe = pd.concat([games_dataframe, temp_games_data_frame])

                games_dataframe = games_dataframe.sort_values(by=['game_id'])

                # Drop unwanted data
                unwanted_columns: list[str] = [
                    'moby_score',
                    'num_votes',
                    'platforms',
                    'sample_cover',
                    'sample_cover.platforms',
                    'sample_cover.height',
                    'sample_cover.image',
                    'sample_cover.thumbnail_image',
                    'sample_cover.width',
                    'sample_screenshots',
                ]

                for column in unwanted_columns:
                    try:
                        games_dataframe.pop(column)
                    except Exception:
                        pass

                # Expand columns that need it
                games_dataframe.insert(0, 'game_id', games_dataframe.pop('game_id'))
                games_dataframe.insert(1, 'title', games_dataframe.pop('title'))

                # Split out alternate titles into their own dataframe
                games_alternate_titles_dataframe = games_dataframe.filter(
                    ['alternate_titles', 'game_id']
                )
                games_dataframe.pop('alternate_titles')

                # Expand alternate titles and add the game ID
                games_alternate_titles_dataframe = games_alternate_titles_dataframe.explode(
                    'alternate_titles', ignore_index=True
                )

                exploded_alternate_titles = pd.json_normalize(
                    games_alternate_titles_dataframe['alternate_titles']  # type: ignore
                )
                exploded_alternate_titles['game_id'] = games_alternate_titles_dataframe['game_id']

                games_alternate_titles_dataframe = exploded_alternate_titles
                games_alternate_titles_dataframe.insert(
                    0, 'game_id', games_alternate_titles_dataframe.pop('game_id')
                )

                # Split out genres into their own dataframe
                genres_dataframe = games_dataframe.filter(['genres', 'game_id'])
                games_dataframe.pop('genres')

                # Expand genres and add the game ID
                genres_dataframe = genres_dataframe.explode('genres', ignore_index=True)

                exploded_genres = pd.json_normalize(genres_dataframe['genres'])  # type: ignore
                exploded_genres['game_id'] = genres_dataframe['game_id']

                genres_dataframe = exploded_genres
                genres_dataframe.insert(0, 'game_id', genres_dataframe.pop('game_id'))

                # Get individual game details data
                games_details: list[dict[str, Any]] = []

                for game_id in game_ids:
                    if pathlib.Path(f'cache/{platform_id}/games-details/{game_id}.json').is_file():
                        with open(
                            pathlib.Path(f'cache/{platform_id}/games-details/{game_id}.json'),
                            encoding='utf-8',
                        ) as games_details_cache:
                            games_details.append(json.load(games_details_cache))

                games_details = sorted(games_details, key=lambda x: x['game_id'])

                # Handle attributes
                attributes_dataframe = pd.json_normalize(
                    data=games_details, record_path='attributes', meta=['game_id'], errors='ignore'
                )
                attributes_dataframe.insert(0, 'game_id', attributes_dataframe.pop('game_id'))

                # Handle releases
                releases_dataframe = pd.json_normalize(
                    data=games_details,
                    record_path=['releases', 'companies'],
                    meta=[
                        'game_id',
                        ['releases', 'countries'],
                        ['releases', 'description'],
                        ['releases', 'release_date'],
                    ],
                    errors='ignore',
                )
                releases_dataframe.insert(0, 'game_id', releases_dataframe.pop('game_id'))
                releases_dataframe.insert(
                    1, 'releases.release_date', releases_dataframe.pop('releases.release_date')
                )

                # Expand the countries list in the releases dataframe
                releases_dataframe = releases_dataframe.explode(
                    'releases.countries', ignore_index=True
                )

                # Handle product codes
                product_codes_dataframe = pd.json_normalize(
                    data=games_details,
                    record_path=['releases', 'product_codes'],
                    meta=['game_id', ['releases', 'release_date']],
                )
                product_codes_dataframe.insert(0, 'game_id', product_codes_dataframe.pop('game_id'))
                product_codes_dataframe.insert(
                    1, 'releases.release_date', product_codes_dataframe.pop('releases.release_date')
                )

                # Handle patches
                patches_dataframe = pd.json_normalize(
                    data=games_details, record_path=['patches'], meta=['game_id']
                )
                patches_dataframe.insert(0, 'game_id', patches_dataframe.pop('game_id'))

                # Handle ratings
                ratings_dataframe = pd.json_normalize(
                    data=games_details, record_path=['ratings'], meta=['game_id']
                )
                ratings_dataframe.insert(0, 'game_id', ratings_dataframe.pop('game_id'))

                eprint('• Organizing game data... done.', indent=False, overwrite=True)

                # Write the output files
                eprint(
                    f'\n{Font.success}Finished processing titles. Writing output files...'
                    f'{Font.end}',
                    indent=False,
                )

                def write_file(dataframe: pd.DataFrame, output_file: str) -> None:
                    # Sanitize the dataframe
                    dataframe = sanitize_dataframes(dataframe)

                    # Write to delimited file, using a BOM so Microsoft apps interpret the encoding correctly
                    dataframe.to_csv(output_file, index=False, encoding='utf-8-sig', sep=delimiter)

                write_file(games_dataframe, f'{prefix}{raw_platform_name} - (Primary) Games.txt')

                if len(games_alternate_titles_dataframe.index) > 0:
                    write_file(
                        games_alternate_titles_dataframe,
                        f'{prefix}{raw_platform_name} - Alternate titles.txt',
                    )

                if len(genres_dataframe.index) > 0:
                    write_file(genres_dataframe, f'{prefix}{raw_platform_name} - Genres.txt')

                if len(attributes_dataframe.index) > 0:
                    write_file(
                        attributes_dataframe, f'{prefix}{raw_platform_name} - Attributes.txt'
                    )

                if len(releases_dataframe.index) > 0:
                    write_file(releases_dataframe, f'{prefix}{raw_platform_name} - Releases.txt')

                if len(product_codes_dataframe.index) > 0:
                    write_file(
                        product_codes_dataframe, f'{prefix}{raw_platform_name} - Product codes.txt'
                    )

                if len(patches_dataframe.index) > 0:
                    write_file(patches_dataframe, f'{prefix}{raw_platform_name} - Patches.txt')

                if len(ratings_dataframe.index) > 0:
                    write_file(ratings_dataframe, f'{prefix}{raw_platform_name} - Ratings.txt')

                eprint(
                    f'{Font.success}Finished processing titles. Writing output files... '
                    f'done.{Font.end}',
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
