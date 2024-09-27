from __future__ import annotations

import datetime
import json
import pathlib
import sys
from typing import Any

import dateutil
import numpy as np
import pandas as pd
from natsort import natsorted

from modules.data_sanitize import replace_invalid_characters, sanitize_dataframes
from modules.requests import api_request, request_wait
from modules.utils import Config, Font, eprint


def add_games(games_dict: dict[str, Any], games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Reworks game data to be suitable for databases, then adds the game to a list.

    Args:
        games_dict (dict[str, Any]): A response from the MobyGames API containing game details.
        games (list[dict[str, Any]]): A list containing game data from MobyGames.

    Returns:
        list[dict[str, Any]]: A list containing game data from MobyGames.
    """
    for game_values in games_dict.values():
        for game_value in game_values:
            games.append(game_value)

    return games


def delete_cache(cache_folder: int | str) -> dict[str, bool | str]:
    """
    Deletes the local cache for a downloaded platform.

    Args:
        cache_folder (int|str): The MobyGames platform ID to delete downloaded data for.

    Returns:
        dict[str, bool]: A reset completion status.
    """
    if cache_folder == 'updates':
        # Delete the updates cache files
        for game_file in pathlib.Path('cache/updates/').glob('*.json'):
            game_file.unlink()

        # Rewrite the status file
        completion_status = {'update_finished': False}

        with open(pathlib.Path('cache/updates.json'), 'w', encoding='utf-8') as status_cache:
            status_cache.write(json.dumps(completion_status, indent=2, ensure_ascii=False))
    else:
        # Delete the game cache files
        for game_file in pathlib.Path(f'cache/{cache_folder}/games/').glob('*.json'):
            game_file.unlink()

        # Delete the game details files
        for game_details_file in pathlib.Path(f'cache/{cache_folder}/games-details/').glob(
            '*.json'
        ):
            game_details_file.unlink()

        # Rewrite the status file
        now = (
            datetime.datetime.now(tz=datetime.timezone.utc)
            .replace(tzinfo=datetime.timezone.utc)
            .astimezone(tz=None)
        )

        completion_status = {
            'stage_1_finished': False,
            'stage_2_finished': False,
            'last_updated': now.strftime("%Y/%m/%d"),
        }

        with open(
            pathlib.Path(f'cache/{cache_folder}/status.json'), 'w', encoding='utf-8'
        ) as status_cache:
            status_cache.write(json.dumps(completion_status, indent=2, ensure_ascii=False))

    return completion_status


def get_games(
    platform_id: int, platform_name: str, completion_status: dict[str, bool | str], config: Config
) -> None:
    """
    Gets the titles, alternate titles, descriptions, URLs, and genres from MobyGames.

    Args:
        platform_id (int): The MobyGames platform ID.
        platform_name (str): The MobyGames platform name.
        completion_status (dict[str, bool]): Which stages MobyDump has finished.
        config (Config): The MobyDump config object instance.
    """
    now: datetime.datetime

    eprint(f'{Font.b}─────────────── Retrieving games from {platform_name} ───────────────{Font.be}\n')
    eprint(f'{Font.b}{Font.u}Stage 1{Font.end}')
    eprint(
        'Getting titles, alternate titles, descriptions, URLs, and genres.\n',
        indent=0,
    )

    # Set the request offset
    offset: int = 0
    offset_increment: int = 100

    # Figure out the last offset's data that has been cached
    if list(pathlib.Path(f'cache/{platform_id}/games/').glob('*.json')):
        offset = (
            max(
                natsorted(
                    [
                        int(x.stem)
                        for x in pathlib.Path(f'cache/{platform_id}/games/').glob('*.json')
                    ]
                )
            )
            + offset_increment
        )

    if offset:
        eprint(f'• Requests were previously interrupted, resuming from offset {offset}')

    # Get all the response pages for a platform, and add the games to a list
    i: int = 0
    end_loop: bool = False

    while True:
        # Wait for the rate limit after the first request
        if i > 0:
            request_wait(config.rate_limit)
        else:
            i += 1

        if not completion_status['stage_1_finished']:
            # Make the request for the platform's games
            now = (
                datetime.datetime.now(tz=datetime.timezone.utc)
                .replace(tzinfo=datetime.timezone.utc)
                .astimezone(tz=None)
            )

            game_dict: dict[str, Any] = api_request(
                f'https://api.mobygames.com/v1/games?api_key={config.api_key}&platform={platform_id}&offset={offset}&limit={offset_increment}',
                config.headers,
                message=f'• [{now.strftime("%Y/%m/%d %H:%M:%S")}] Requesting titles {offset}-{offset+offset_increment}...',
            ).json()

            # Increment the offset
            offset = offset + offset_increment

            # Break the loop if MobyGames returns an empty response or if there's less than 100 titles, as we've
            # reached the end
            if 'games' in game_dict:
                now = (
                    datetime.datetime.now(tz=datetime.timezone.utc)
                    .replace(tzinfo=datetime.timezone.utc)
                    .astimezone(tz=None)
                )

                eprint(
                    f'• [{now.strftime("%Y/%m/%d %H:%M:%S")}] Requesting titles {offset-offset_increment}-{offset}... done.\n',
                    overwrite=True,
                )

                if len(game_dict['games']) < 100:
                    completion_status['stage_1_finished'] = True
                    end_loop = True

            else:
                completion_status['stage_1_finished'] = True
                end_loop = True
        else:
            end_loop = True

        # Write the cache
        with open(
            pathlib.Path(f'cache/{platform_id}/games/{offset-offset_increment!s}.json'),
            'w',
            encoding='utf-8',
        ) as platform_request_cache:
            platform_request_cache.write(json.dumps(game_dict, separators=(',', ':'), ensure_ascii=False))

        # Write the completion status
        with open(
            pathlib.Path(f'cache/{platform_id}/status.json'), 'w', encoding='utf-8'
        ) as status_cache:
            status_cache.write(json.dumps(completion_status, indent=2, ensure_ascii=False))

        # End the loop if needed
        if end_loop:
            break


def get_game_details(
    platform_id: int, platform_name: str, completion_status: dict[str, bool | str], config: Config
) -> None:
    """
    Gets the attributes, patches, ratings, and releases for each game from MobyGames.

    Args:
        platform_id (int): The MobyGames platform ID.
        platform_name (str): The MobyGames platform name.
        completion_status (dict[str, bool]): Which stages MobyDump has finished.
        config (Config): The MobyDump config object instance.
    """
    now: datetime.datetime

    if list(pathlib.Path(f'cache/{platform_id}/games-details/').glob('*.json')):
        eprint(f'{Font.b}─────────────── Retrieving games from {platform_name} ⎯⎯⎯⎯⎯──────────{Font.be}')

    eprint(
        f'\n{Font.b}{Font.u}Stage 2{Font.end}\nGetting attributes, patches, ratings, and releases for each game.\n',
        indent=0,
    )

    # Show a resume message if needed
    if list(pathlib.Path(f'cache/{platform_id}/games-details/').glob('*.json')):
        eprint('• Requests were previously interrupted, resuming...')

    # Get the game count
    files: list[pathlib.Path] = natsorted(
        list(pathlib.Path(f'cache/{platform_id}/games/').glob('*.json'))
    )
    file_count: int = len(files)
    game_count: int = file_count * 100 - 100

    with open(pathlib.Path(files[-1]), encoding='utf-8') as platform_request_cache:
        cache: dict[str, Any] = json.loads(platform_request_cache.read())

        game_count = game_count + len(cache['games'])

    game_iterator: int = 0

    for game_file in natsorted(pathlib.Path(f'cache/{platform_id}/games/').glob('*.json')):

        # Get the game IDs to download details for
        games: list[tuple[int, str]] = []

        with open(pathlib.Path(game_file), encoding='utf-8') as platform_request_cache:
            cache: dict[str, Any] = json.loads(platform_request_cache.read())

            games = get_game_ids_and_titles(cache)

        # Only download game details that haven't been downloaded yet
        for game in games:
            game_iterator += 1

            game_id = game[0]
            game_title = game[1]

            if not pathlib.Path(f'cache/{platform_id}/games-details/{game_id}.json').is_file():
                now = (
                    datetime.datetime.now(tz=datetime.timezone.utc)
                    .replace(tzinfo=datetime.timezone.utc)
                    .astimezone(tz=None)
                )

                game_details: dict[str, Any] = api_request(
                    f'https://api.mobygames.com/v1/games/{game_id}/platforms/{platform_id}?api_key={config.api_key}',
                    config.headers,
                    message=f'• [{now.strftime("%Y/%m/%d %H:%M:%S")}] Requesting details for {game_title} [ID: {game_id}] ({game_iterator:,}/{game_count:,})...',
                ).json()

                with open(
                    pathlib.Path(f'cache/{platform_id}/games-details/{game_id}.json'),
                    'w',
                    encoding='utf-8',
                ) as game_details_cache:
                    game_details_cache.write(json.dumps(game_details, separators=(',', ':'), ensure_ascii=False))

                now = (
                    datetime.datetime.now(tz=datetime.timezone.utc)
                    .replace(tzinfo=datetime.timezone.utc)
                    .astimezone(tz=None)
                )

                eprint(
                    f'• [{now.strftime("%Y/%m/%d %H:%M:%S")}] Requesting details for {game_title} [ID: {game_id}] ({game_iterator:,}/{game_count:,})... done.\n',
                    overwrite=True,
                    wrap=False,
                )

                request_wait(config.rate_limit)

    # Write the completion status
    completion_status['stage_2_finished'] = True

    with open(
        pathlib.Path(f'cache/{platform_id}/status.json'), 'w', encoding='utf-8'
    ) as status_cache:
        status_cache.write(json.dumps(completion_status, indent=2, ensure_ascii=False))


def get_game_ids_and_titles(cache: dict[str, Any]) -> list[tuple[int, str]]:
    """
    Extracts game IDs and titles from a cache file.

    Args:
        cache (dict[str, Any]): A MobyDump cache file.

    Returns:
        list[tuple[int, str]]: Game IDs and titles.
    """
    games: list[tuple[int, str]] = []

    for cached_game in cache['games']:
        game_id: int = 0
        game_title: str = ''

        for key, value in cached_game.items():
            if key == 'game_id':
                game_id = value
            elif key == 'title':
                game_title = value

            if game_id and game_title:
                games.append((game_id, game_title))
                break

    return games


def get_platforms(config: Config) -> dict[str, list[dict[str, str | int]]]:
    """
    Make the platform request, and write the results to a JSON file for an offline
    cache.

    config (Config): The MobyDump config object instance.

    Returns:
        dict[str, list[dict[str, str | int]]]: The contents of the response, in JSON form.
    """
    platforms: dict[str, list[dict[str, str | int]]] = api_request(
        f'https://api.mobygames.com/v1/platforms?api_key={config.api_key}',
        config.headers,
        message='• Retrieving platforms...',
    ).json()

    eprint('• Retrieving platforms... done.', overwrite=True)

    # Store the response in a file
    if not pathlib.Path('cache').is_dir():
        pathlib.Path('cache').mkdir(parents=True, exist_ok=True)

    with open(pathlib.Path('cache/platforms.json'), 'w', encoding='utf-8') as platform_cache:
        platform_cache.write(json.dumps(platforms, indent=2, ensure_ascii=False))

    return platforms


def get_updates(config: Config) -> None:
    """

    Get updates from MobyGames, then check the ages of existing downloads in the cache
    and update accordinglt.

    Args:
        config (Config): The MobyDump config object instance.
        number_of_days (int): The number of days of updates to request. The maximum is 21.
    """
    eprint(f'{Font.b}{Font.u}Updates{Font.end}')
    eprint(
        'Getting game updates.\n',
        indent=0,
    )

    # Get the completion status
    completion_status = {'update_finished': False}

    if pathlib.Path('cache/updates.json').is_file():
        with open(pathlib.Path('cache/updates.json'), encoding='utf-8') as status_cache:
            try:
                completion_status = json.load(status_cache)
            except Exception:
                pass

    resume: str = ''

    if not config.args.forcerestart:
        if completion_status['update_finished']:

            while resume != 'r' and resume != 'w' and resume != 'q':
                eprint(
                    '\nUpdates have already been downloaded. Do you want to redownload (r), write new output '
                    'files from cache (w), or exit (q)?',
                    level='warning',
                    indent=0,
                )
                resume = input('\n> ')
                eprint('')

    if resume == 'r' or config.args.forcerestart:
        completion_status = delete_cache('updates')
    elif resume == 'q':
        sys.exit()

    # Start the update requests
    if not completion_status['update_finished']:
        # Set the request offset
        offset: int = 0
        offset_increment: int = 100

        # Figure out the last offset's data that has been cached
        if list(pathlib.Path('cache/updates/').glob('*.json')):
            offset = (
                max(natsorted([int(x.stem) for x in pathlib.Path('cache/updates/').glob('*.json')]))
                + offset_increment
            )

        if offset:
            eprint(f'• Requests were previously interrupted, resuming from offset {offset}')

        # Get all response pages for an update, and add the games to a list
        i: int = 0
        end_loop: bool = False

        updated_games: list[dict[str, Any]] = []

        while True:
            # Wait for the rate limit after the first request
            if i > 0:
                request_wait(config.rate_limit)
            else:
                i += 1

            # Make the request for updated games
            now = (
                datetime.datetime.now(tz=datetime.timezone.utc)
                .replace(tzinfo=datetime.timezone.utc)
                .astimezone(tz=None)
            )

            game_dict: dict[str, Any] = api_request(
                f'https://api.mobygames.com/v1/games/recent?api_key={config.api_key}&format=normal&age={config.args.update}&offset={offset}&limit={offset_increment}',
                config.headers,
                message=f'• [{now.strftime("%H:%M:%S")}] Requesting updated titles {offset}-{offset+offset_increment}...',
            ).json()

            # Increment the offset
            offset = offset + offset_increment

            # Break the loop if MobyGames returns an empty response or if there's less than 100 titles, as we've
            # reached the end
            if 'games' in game_dict:
                now = (
                    datetime.datetime.now(tz=datetime.timezone.utc)
                    .replace(tzinfo=datetime.timezone.utc)
                    .astimezone(tz=None)
                )

                eprint(
                    f'• [{now.strftime("%H:%M:%S")}] Requesting updated titles {offset-offset_increment}-{offset}... done.\n',
                    overwrite=True,
                )

                if len(game_dict['games']) < 100:
                    completion_status['update_finished'] = True
                    end_loop = True

            else:
                completion_status['update_finished'] = True
                end_loop = True

            for game in game_dict['games']:
                updated_games.append(game)

            # Write the cache
            with open(
                pathlib.Path(f'cache/updates/{offset-offset_increment!s}.json'),
                'w',
                encoding='utf-8',
            ) as platform_request_cache:
                platform_request_cache.write(json.dumps(game_dict, separators=(',', ':'), ensure_ascii=False))

            # Write the completion status
            with open(pathlib.Path('cache/updates.json'), 'w', encoding='utf-8') as status_cache:
                status_cache.write(json.dumps(completion_status, indent=2, ensure_ascii=False))

            # End the loop if needed
            if end_loop:
                break

    if completion_status['update_finished']:
        # Get the platform IDs
        if not pathlib.Path('cache/platforms.json').is_file():
            get_platforms(config)
            request_wait(config.rate_limit)

        platforms: dict[str, int] = {}

        with open(pathlib.Path('cache/platforms.json'), encoding='utf-8') as platform_cache:
            platforms = json.loads(platform_cache.read())['platforms']

            platforms = sorted(platforms, key=lambda x: x['platform_id'])

        # Update per platform
        for platform in platforms:
            # Check the last updated dates for each platform
            last_updated: datetime.datetime | None = None

            if pathlib.Path(f'cache/{platform["platform_id"]}').is_dir():
                if pathlib.Path(f'cache/{platform["platform_id"]}/status.json').is_file():
                    with open(
                        pathlib.Path(f'cache/{platform["platform_id"]}/status.json'),
                        encoding='utf-8',
                    ) as status_cache:
                        try:
                            completion_status = json.load(status_cache)
                        except Exception:
                            pass

                    if (
                        completion_status['stage_1_finished']
                        and completion_status['stage_2_finished']
                    ):
                        if 'last_updated' in completion_status:
                            last_updated = (
                                datetime.datetime.strptime(
                                    completion_status['last_updated'], '%Y/%m/%d'
                                )
                                .replace(tzinfo=datetime.timezone.utc)
                                .astimezone(tz=None)
                            )
                    else:
                        eprint(
                            f'The {platform["platform_name"]} platform hasn\'t finished downloading yet, so can\'t be updated.\nComplete the download first with {Font.b}-g {platform["platform_id"]}{Font.be}\n',
                            level='warning',
                            indent=0,
                            wrap=False,
                        )
                        continue

            if last_updated:
                now = (
                    datetime.datetime.now(tz=datetime.timezone.utc)
                    .replace(tzinfo=datetime.timezone.utc)
                    .astimezone(tz=None)
                )

                rd = dateutil.relativedelta.relativedelta(now, last_updated)

                if not rd.months and rd.days < 21:
                    eprint(
                        f'{Font.b}Updating the {platform["platform_name"]} platform{Font.be} ({platform["platform_id"]})'
                    )

                    # Read from the update cache
                    updated_games: list[dict[str, Any]] = []

                    for game_file in pathlib.Path('cache/updates/').glob('*.json'):
                        with open(pathlib.Path(game_file), encoding='utf-8') as update_cache:
                            cache = json.loads(update_cache.read())

                            updated_games.extend(cache['games'])

                    # Split by platform
                    updated_platform_related_games: list[dict[str, Any]] = []
                    updated_platform_unrelated_games: list[dict[str, Any]] = []

                    for updated_game in updated_games:
                        found_platform: bool = False

                        for platform_release in updated_game['platforms']:
                            if platform_release['platform_id'] == platform["platform_id"]:
                                updated_platform_related_games.append(updated_game)
                                found_platform = True

                        if not found_platform:
                            updated_platform_unrelated_games.append(updated_game)

                    if updated_platform_related_games or updated_platform_unrelated_games:
                        # Get all the game IDs for the platform
                        game_ids: set[int] = set()

                        for game_file in pathlib.Path(
                            f'cache/{platform["platform_id"]}/games/'
                        ).glob('*.json'):
                            with open(
                                pathlib.Path(game_file), encoding='utf-8'
                            ) as platform_request_cache:
                                cache = json.loads(platform_request_cache.read())

                                game_ids = game_ids | {x['game_id'] for x in cache['games']}

                        # Add in game IDs if they don't exist
                        game_ids = game_ids | {x['game_id'] for x in updated_platform_related_games}

                        # Remove game IDs if they should be deleted
                        removed_game_ids: set[int] = set()

                        for removed_game_id in {
                            x['game_id'] for x in updated_platform_unrelated_games
                        }:
                            if removed_game_id in game_ids:
                                game_ids.remove(removed_game_id)
                                removed_game_ids.add(removed_game_id)

                        # Recreate the cached files in the games folder
                        added_game_ids: set[int] = set()
                        file_contents: list[str, Any] = []
                        file_count: int = 0
                        last_id: int = 0
                        cache = {}

                        eprint('• Updating cache files...')

                        for game_id in sorted(game_ids):
                            # Check the updated list for the game ID first
                            for updated_platform_related_game in updated_platform_related_games:
                                if updated_platform_related_game['game_id'] == game_id:
                                    file_contents.append(updated_platform_related_game)
                                    added_game_ids.add(game_id)
                                    break

                            # Check the cache files for the game ID
                            if game_id not in added_game_ids:
                                try:
                                    if game_id > last_id:
                                        with open(
                                            pathlib.Path(
                                                f'cache/{platform["platform_id"]}/games/{100*file_count}.json'
                                            ),
                                            encoding='utf-8',
                                        ) as platform_request_cache:
                                            cache = json.loads(platform_request_cache.read())

                                    # Get the last ID in the cache file, and if we've exceeded it, don't check this file again
                                    last_id: int = max([x['game_id'] for x in cache['games']])

                                    # Grab the game ID entry from the cache file
                                    file_contents.extend(
                                        [x for x in cache['games'] if x['game_id'] == game_id]
                                    )
                                    added_game_ids.add(game_id)
                                except Exception:
                                    pass

                            # Check if modulo 100 == 0 or if it's the last game ID, and if so, write a temporary output file
                            if not len(file_contents) % 100 or game_id == sorted(game_ids)[-1]:
                                json_contents: list[str] = json.dumps(
                                    file_contents, indent=2, ensure_ascii=False
                                ).split('\n')

                                with open(
                                    pathlib.Path(
                                        f'cache/{platform["platform_id"]}/games/{100*file_count}.jsontmp'
                                    ),
                                    'w',
                                    encoding='utf-8',
                                ) as platform_request_cache:
                                    platform_request_cache.write('{\n  "games": ')
                                    for i, line in enumerate(json_contents):
                                        if i == 0:
                                            platform_request_cache.write(f'{line}\n')
                                        elif i == len(json_contents) - 1:
                                            platform_request_cache.write(f'  {line}')
                                        else:
                                            platform_request_cache.write(f'  {line}\n')
                                    platform_request_cache.write('  \n}')

                                file_contents = []
                                file_count += 1

                        # Rename temporary files to overwrite the existing cache files
                        for game_file in natsorted(
                            pathlib.Path(f'cache/{platform["platform_id"]}/games/').glob(
                                '*.jsontmp'
                            )
                        ):
                            game_file.replace(
                                pathlib.Path(
                                    f'{pathlib.Path(game_file.parent).joinpath(game_file.stem)}.json'
                                )
                            )

                        # Update cache file
                        now = (
                            datetime.datetime.now(tz=datetime.timezone.utc)
                            .replace(tzinfo=datetime.timezone.utc)
                            .astimezone(tz=None)
                        )

                        completion_status: dict[str, bool] = {
                            'stage_1_finished': True,
                            'stage_2_finished': True,
                            'last_updated': now.strftime("%Y/%m/%d"),
                        }

                        with open(
                            pathlib.Path(f'cache/{platform["platform_id"]}/status.json'),
                            'w',
                            encoding='utf-8',
                        ) as status_cache:
                            status_cache.write(
                                json.dumps(completion_status, indent=2, ensure_ascii=False)
                            )

                        eprint('• Updating cache files... done.', overwrite=True)

                        # Download new and updated game details, and remove game details files for those games that have been removed from the platform
                        if updated_platform_related_games:
                            eprint(
                                f'• {len(updated_platform_related_games)} game IDs changed or were added: {", ".join([str(x["game_id"]) for x in sorted(updated_platform_related_games, key=lambda x: x["game_id"])])}'
                            )
                            eprint('• Downloading updated game details.')

                            # Get the updated game details
                            game_iterator = 0

                            for updated_platform_related_game in sorted(
                                updated_platform_related_games, key=lambda x: x['game_id']
                            ):
                                game_id = updated_platform_related_game['game_id']
                                game_title = updated_platform_related_game['title']
                                game_count = len(updated_platform_related_games)
                                game_iterator += 1

                                now = (
                                    datetime.datetime.now(tz=datetime.timezone.utc)
                                    .replace(tzinfo=datetime.timezone.utc)
                                    .astimezone(tz=None)
                                )

                                game_details: dict[str, Any] = api_request(
                                    f'https://api.mobygames.com/v1/games/{game_id}/platforms/{platform["platform_id"]}?api_key={config.api_key}',
                                    config.headers,
                                    message=f'• [{now.strftime("%Y/%m/%d %H:%M:%S")}] Requesting details for {game_title} [ID: {game_id}] ({game_iterator:,}/{game_count:,})...',
                                ).json()

                                with open(
                                    pathlib.Path(
                                        f'cache/{platform["platform_id"]}/games-details/{game_id}.json'
                                    ),
                                    'w',
                                    encoding='utf-8',
                                ) as game_details_cache:
                                    game_details_cache.write(
                                        json.dumps(game_details, separators=(',', ':'), ensure_ascii=False)
                                    )

                                now = (
                                    datetime.datetime.now(tz=datetime.timezone.utc)
                                    .replace(tzinfo=datetime.timezone.utc)
                                    .astimezone(tz=None)
                                )

                                eprint(
                                    f'• [{now.strftime("%Y/%m/%d %H:%M:%S")}] Requesting details for {game_title} [ID: {game_id}] ({game_iterator:,}/{game_count:,})... done.\n',
                                    overwrite=True,
                                    wrap=False,
                                )

                                request_wait(config.rate_limit)

                        if removed_game_ids:
                            eprint(
                                f'• {len(removed_game_ids)} game IDs were removed: {", ".join([str(x) for x in sorted(removed_game_ids)])}'
                            )
                            eprint('• Deleting removed games from the cache...')
                            for game_id in removed_game_ids:
                                if pathlib.Path(
                                    f'cache/{platform["platform_id"]}/games-details/{game_id}.json'
                                ).is_file():
                                    pathlib.Path(
                                        f'cache/{platform["platform_id"]}/games-details/{game_id}.json'
                                    ).unlink()

                            eprint(
                                '• Deleting removed games from the cache... done', overwrite=True
                            )

                        # Write out the files for the platform
                        write_output_files(
                            config,
                            platform["platform_id"],
                            platform["platform_name"],
                            update=True,
                        )
                    else:
                        eprint('• No games needed to be updated.')
                else:
                    eprint(
                        f'• Not updating the {platform["platform_name"]} platform, as it\'s been more than 21 days since it was last updated. Redownload the platform from scratch to capture the updated game details.',
                        level='warning',
                    )
                    continue


def write_output_files(
    config: Config, platform_id: int, platform_name: str, update: bool = False
) -> None:
    """
    Writes files based on downloaded MobyGames data in multiple formats.

    Args:
        config (Config): The MobyDump config object instance.
        platform_id (int): The MobyGames platform ID.
        platform_name (str): The MobyGames platform name.
        update (bool): Whether an update is being run.
    """
    # Create the output path
    if config.output_path:
        pathlib.Path(config.output_path).mkdir(parents=True, exist_ok=True)

    # Don't write files
    if config.output_file_type == 0:
        eprint(
            '• Finished processing titles.\n',
            wrap=False,
        )
    # Write the output file in JSON
    elif config.output_file_type == 2:
        eprint(
            f'\n{Font.success}Finished processing titles. Writing output file...{Font.end}',
            indent=0,
        )

        # Enrich games with individual game details, and write to the JSON file
        for game_file in pathlib.Path(f'cache/{platform_id}/games/').glob('*.json'):
            with open(pathlib.Path(game_file), encoding='utf-8') as platform_request_cache:
                cache: dict[str, Any] = json.loads(platform_request_cache.read())

                output_file: str = f'{config.prefix}{platform_name}.json'
                output_file = pathlib.Path(config.output_path).joinpath(output_file)

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
                            loaded_game_details: dict[str, Any] = json.load(game_details_cache)

                            # Add the game details keys to the game
                            for key, values in loaded_game_details.items():
                                game[key] = values

                            # Sort alphabetically by key
                            game = dict(sorted(game.items()))

                            # Move game ID and title to the top
                            game = {'game_id': game.pop('game_id'), **game}
                            game = {'title': game.pop('title'), **game}

                            with open(pathlib.Path(output_file), 'a', encoding='utf-8-sig') as file:
                                game_json: str = json.dumps(game, indent=2, ensure_ascii=False)

                                if i + 1 < len(cache['games']):
                                    game_json = f'{game_json},'

                                for line in game_json.split('\n'):
                                    file.write(f'    {line}\n')

                # Close the file
                with open(pathlib.Path(output_file), 'a', encoding='utf-8-sig') as file:
                    file.write('  ]\n}\n')

        eprint(
            f'{Font.success}Finished processing titles. Writing output file... '
            f'done.{Font.end}\n\n',
            overwrite=True,
            wrap=False,
        )
    # Write the output files as delimiter separated value files
    elif config.output_file_type == 1:
        # Organize the data into separate tables for output, as Access can't
        # handle more than 255 columns of data, and the API returns data of
        # different shapes
        eprint(
            '• Organizing game data...',
            indent=0,
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
        games_alternate_titles_dataframe = games_dataframe.filter(['alternate_titles', 'game_id'])
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
                    try:
                        games_details.append(json.load(games_details_cache))
                    except Exception:
                        game_details: dict[str, Any] = api_request(
                            f'https://api.mobygames.com/v1/games/{game_id}/platforms/{platform_id}?api_key={config.api_key}',
                            config.headers,
                            message=f'• [Re-requesting details for game ID: {game_id}, as it seems to be corrupt...',
                        ).json()

                        with open(
                            pathlib.Path(f'cache/{platform_id}/games-details/{game_id}.json'),
                            'w',
                            encoding='utf-8',
                        ) as game_details_cache:
                            game_details_cache.write(
                                json.dumps(game_details, separators=(',', ':'), ensure_ascii=False)
                            )

                        eprint(
                            f'• [Re-requesting details for game ID: {game_id}, as it seems to be corrupt... done.',
                            overwrite=True,
                        )

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
        releases_dataframe = releases_dataframe.explode('releases.countries', ignore_index=True)

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

        eprint('• Organizing game data... done.', indent=0, overwrite=True)

        # Write the output files
        if update:
            eprint('• Finished processing titles. Writing output files...', indent=0)
        else:
            eprint(
                f'\n{Font.success}Finished processing titles. Writing output files...'
                f'{Font.end}',
                indent=0,
            )

        def write_file(dataframe: pd.DataFrame, output_file: str) -> None:
            # Sanitize the dataframe
            dataframe = sanitize_dataframes(dataframe)

            # Write to delimited file, using a BOM so Microsoft apps interpret the encoding correctly
            dataframe.to_csv(output_file, index=False, encoding='utf-8-sig', sep=config.delimiter)

        file_platform_name: str = replace_invalid_characters(platform_name)

        output_path_prefix: pathlib.Path = pathlib.Path(config.output_path).joinpath(
            f'{config.prefix}{file_platform_name}'
        )

        write_file(games_dataframe, f'{output_path_prefix} - (Primary) Games.txt')

        if len(games_alternate_titles_dataframe.index) > 0:
            write_file(
                games_alternate_titles_dataframe,
                f'{output_path_prefix} - Alternate titles.txt',
            )

        if len(genres_dataframe.index) > 0:
            write_file(genres_dataframe, f'{output_path_prefix} - Genres.txt')

        if len(attributes_dataframe.index) > 0:
            write_file(attributes_dataframe, f'{output_path_prefix} - Attributes.txt')

        if len(releases_dataframe.index) > 0:
            write_file(releases_dataframe, f'{output_path_prefix} - Releases.txt')

        if len(product_codes_dataframe.index) > 0:
            write_file(product_codes_dataframe, f'{output_path_prefix} - Product codes.txt')

        if len(patches_dataframe.index) > 0:
            write_file(patches_dataframe, f'{output_path_prefix} - Patches.txt')

        if len(ratings_dataframe.index) > 0:
            write_file(ratings_dataframe, f'{output_path_prefix} - Ratings.txt')

        if update:
            eprint(
                '• Finished processing titles. Writing output files... done.\n\n',
                indent=0,
                overwrite=True,
            )
        else:
            eprint(
                f'{Font.success}Finished processing titles. Writing output files... '
                f'done.{Font.end}',
                overwrite=True,
                wrap=False,
            )
