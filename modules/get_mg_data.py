from __future__ import annotations

import datetime
import json
import os
import pathlib
import shutil
import sys
import zipfile
from typing import TYPE_CHECKING, Any

import dateutil
import dropbox
import numpy as np
import pandas as pd
from compress_json import compress, decompress  # pip install compress-json-python
from discord import SyncWebhook
from dropbox.exceptions import ApiError, AuthError
from dropbox.files import WriteMode
from natsort import natsorted

from modules.data_sanitize import (
    better_platform_name,
    replace_invalid_characters,
    sanitize_dataframes,
)
from modules.requests import api_request, download_file, get_dropbox_short_lived_token, request_wait
from modules.utils import Config, Font, eprint

if TYPE_CHECKING:
    import requests


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


def delete_cache(cache_folder: int | str, config: Config) -> dict[str, bool | str]:
    """
    Deletes the local cache for a downloaded platform.

    Args:
        cache_folder (int|str): The MobyGames platform ID to delete downloaded data for.
        config (Config): The MobyDump config object instance.

    Returns:
        dict[str, bool]: A reset completion status.
    """
    if cache_folder == 'updates':
        # Delete the updates cache files
        for game_file in pathlib.Path(config.cache).joinpath('updates/').glob('*.json'):
            game_file.unlink()

        # Rewrite the status file
        completion_status = {
            'update_finished': False,
            'update_last_run': get_datetime().strftime("%Y/%m/%d %H:%M"),
        }

        with open(
            pathlib.Path(config.cache).joinpath('updates.json'), 'w', encoding='utf-8'
        ) as status_cache:
            status_cache.write(json.dumps(completion_status, indent=2, ensure_ascii=False))
    else:
        # Delete the game cache files
        for game_file in (
            pathlib.Path(config.cache).joinpath(f'{cache_folder}/games/').glob('*.json')
        ):
            game_file.unlink()

        # Delete the game details files
        if not config.args.skipdetails:
            for game_details_file in (
                pathlib.Path(config.cache).joinpath(f'{cache_folder}/games-details/').glob('*.json')
            ):
                game_details_file.unlink()

        # Rewrite the status file
        completion_status = {
            'stage_1_finished': False,
            'stage_2_finished': False,
            'last_updated': get_datetime().strftime("%Y/%m/%d"),
        }

        with open(
            pathlib.Path(config.cache).joinpath(f'{cache_folder}/status.json'),
            'w',
            encoding='utf-8',
        ) as status_cache:
            status_cache.write(json.dumps(completion_status, indent=2, ensure_ascii=False))

    return completion_status


def get_datetime() -> datetime.datetime:
    """
    Convenience wrapper to get the current date and time.

    Returns:
        datetime.datetime: The current date and time.
    """
    return (
        datetime.datetime.now(tz=datetime.timezone.utc)
        .replace(tzinfo=datetime.timezone.utc)
        .astimezone(tz=None)
    )


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
    platform_str_length: int = len(f'Retrieving games from {platform_name} [ID: {platform_id}]')
    horizontal_line_length: int = int((80 - platform_str_length - 10) / 2)
    horizontal_line: str = '─' * horizontal_line_length

    eprint(
        f'{Font.b}{horizontal_line} Retrieving games from {platform_name} [ID: {platform_id}] {horizontal_line}{Font.be}\n'
    )
    eprint(f'{Font.b}{Font.u}Stage 1{Font.end}')
    eprint(
        'Getting titles, alternate titles, descriptions, URLs, and genres.\n',
        indent=0,
    )

    # Set the request offset
    offset: int = 0
    offset_increment: int = 100

    # Figure out the last offset's data that has been cached
    if list(pathlib.Path(config.cache).joinpath(f'{platform_id}/games/').glob('*.json')):
        offset = (
            max(
                natsorted(
                    [
                        int(x.stem)
                        for x in pathlib.Path(config.cache)
                        .joinpath(f'{platform_id}/games/')
                        .glob('*.json')
                    ]
                )
            )
            + offset_increment
        )

    if offset:
        eprint(f'• Requests were previously interrupted, resuming from offset {offset}')

    # Get all the response pages for a platform, and add the games to a list
    end_loop: bool = False

    while True:
        if not completion_status['stage_1_finished']:
            # Make the request for the platform's games
            game_dict: dict[str, Any] = api_request(
                f'https://api.mobygames.com/v1/games?api_key={config.api_key}&platform={platform_id}&offset={offset}&limit={offset_increment}',
                config,
                message=f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Requesting titles {offset}-{offset+offset_increment}...',
            ).json()

            # Increment the offset
            offset = offset + offset_increment

            # Break the loop if MobyGames returns an empty response
            if 'games' in game_dict:
                # Strip the sample_screenshots array
                for game in game_dict['games']:
                    try:
                        del game['sample_screenshots']
                    except Exception:
                        pass

                # Break the loop if there's less than 100 titles, as we've reached the end
                eprint(
                    f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Requesting titles {offset-offset_increment}-{offset}... done.\n',
                    overwrite=True,
                )

                if len(game_dict['games']) < 100:
                    completion_status['stage_1_finished'] = True
                    end_loop = True

                # Handle when the platform has no games
                if len(game_dict['games']) == 0 and offset - offset_increment == 0:
                    eprint(
                        f'\nLooks like {platform_name} has no games, exiting...', level='warning'
                    )
                    shutil.rmtree(pathlib.Path(config.cache).joinpath(f'{platform_id}'))
                    sys.exit(1)

                request_wait(config)
            else:
                completion_status['stage_1_finished'] = True
                end_loop = True
        else:
            end_loop = True

        # Write the cache
        with open(
            pathlib.Path(config.cache).joinpath(
                f'{platform_id}/games/{offset-offset_increment!s}.json'
            ),
            'w',
            encoding='utf-8',
        ) as platform_request_cache:
            platform_request_cache.write(
                json.dumps(compress(game_dict), separators=(',', ':'), ensure_ascii=False)
            )

        # Write the completion status
        with open(
            pathlib.Path(config.cache).joinpath(f'{platform_id}/status.json'), 'w', encoding='utf-8'
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
    if not config.args.skipdetails:
        platform_str_length: int = len(f'Retrieving games from {platform_name} [ID: {platform_id}]')
        horizontal_line_length: int = int((80 - platform_str_length - 10) / 2)
        horizontal_line: str = '─' * horizontal_line_length

        if list(
            pathlib.Path(config.cache).joinpath(f'{platform_id}/games-details/').glob('*.json')
        ):
            eprint(
                f'{Font.b}{horizontal_line} Retrieving games from {platform_name} [ID: {platform_id}] {horizontal_line}{Font.be}\n'
            )

        eprint(
            f'\n{Font.b}{Font.u}Stage 2{Font.end}\nGetting attributes, patches, ratings, and releases for each game.\n',
            indent=0,
        )

        # Show a resume message if needed
        if list(
            pathlib.Path(config.cache).joinpath(f'{platform_id}/games-details/').glob('*.json')
        ):
            eprint('• Requests were previously interrupted, resuming...')

        # Get the game count
        files: list[pathlib.Path] = natsorted(
            list(pathlib.Path(config.cache).joinpath(f'{platform_id}/games/').glob('*.json'))
        )
        file_count: int = len(files)
        game_count: int = file_count * 100 - 100

        with open(pathlib.Path(files[-1]), encoding='utf-8') as platform_request_cache:
            cache: dict[str, Any] = json.loads(platform_request_cache.read())

            try:
                cache = decompress(cache)
            except Exception:
                pass

            game_count = game_count + len(cache['games'])

        game_iterator: int = 0

        for game_file in natsorted(
            pathlib.Path(config.cache).joinpath(f'{platform_id}/games/').glob('*.json')
        ):

            # Get the game IDs to download details for
            games: list[tuple[int, str]] = []

            with open(pathlib.Path(game_file), encoding='utf-8') as platform_request_cache:
                cache: dict[str, Any] = json.loads(platform_request_cache.read())

                try:
                    cache = decompress(cache)
                except Exception:
                    pass

                games = get_game_ids_and_titles(cache)

            # Only download game details that haven't been downloaded yet
            for game in games:
                game_iterator += 1

                game_id = game[0]
                game_title = game[1]

                if (
                    not pathlib.Path(config.cache)
                    .joinpath(f'{platform_id}/games-details/{game_id}.json')
                    .is_file()
                ):
                    if not config.time_estimate_given:
                        eta_string: str = time_estimate(config, game_count, game_iterator)

                        eprint(
                            f'{Font.heading}• Estimated completion time: {eta_string} (doesn\'t account for retries or response delays){Font.end}',
                            wrap=False,
                        )

                        config.time_estimate_given = True

                    game_response: requests.models.Response = api_request(
                        f'https://api.mobygames.com/v1/games/{game_id}/platforms/{platform_id}?api_key={config.api_key}',
                        config,
                        message=f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Requesting details for {game_title} [ID: {game_id}] ({game_iterator:,}/{game_count:,})...',
                        type='game-details',
                    )

                    if game_response.status_code == 404:
                        request_wait(config)
                        continue

                    game_details: dict[str, Any] = game_response.json()

                    with open(
                        pathlib.Path(config.cache).joinpath(
                            f'{platform_id}/games-details/{game_id}.json'
                        ),
                        'w',
                        encoding='utf-8',
                    ) as game_details_cache:
                        game_details_cache.write(
                            json.dumps(
                                compress(game_details), separators=(',', ':'), ensure_ascii=False
                            )
                        )

                    eprint(
                        f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Requesting details for {game_title} [ID: {game_id}] ({game_iterator:,}/{game_count:,})... done.\n',
                        overwrite=True,
                        wrap=False,
                    )

                    request_wait(config)

    # Write the completion status
    completion_status['stage_2_finished'] = True

    with open(
        pathlib.Path(config.cache).joinpath(f'{platform_id}/status.json'), 'w', encoding='utf-8'
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
        config,
        message='• Retrieving platforms...',
    ).json()

    # Get the latest platform-names.json file to map low detail MobyGames platform names
    # to names that include manufacturers
    if not pathlib.Path('.dev').is_file():
        download_file(
            'https://raw.githubusercontent.com/unexpectedpanda/mobydump/refs/heads/main/platform-names.json',
            pathlib.Path('platform-names.json'),
        )

    for platform in platforms['platforms']:
        platform['platform_name'] = better_platform_name(platform['platform_name'])

    eprint('• Retrieving platforms... done.', overwrite=True)

    # Store the response in a file
    if not pathlib.Path(config.cache).is_dir():
        pathlib.Path(config.cache).mkdir(parents=True, exist_ok=True)

    with open(
        pathlib.Path(config.cache).joinpath('platforms.json'), 'w', encoding='utf-8'
    ) as platform_cache:
        platform_cache.write(json.dumps(platforms, indent=2, ensure_ascii=False))

    return platforms


def get_updates(config: Config) -> None:
    """

    Get updates from MobyGames, then check the ages of existing downloads in the cache
    and update accordingly.

    Args:
        config (Config): The MobyDump config object instance.
    """
    discord_webhook: SyncWebhook | None = None

    if config.args.discord:
        if os.getenv('DISCORD_WEBHOOK'):
            discord_webhook = SyncWebhook.from_url(str(os.getenv('DISCORD_WEBHOOK')))
        else:
            eprint(
                '\nMobyDump needs a Discord webhook to continue. For instructions, see'
                '\nthe readme.'
                '\n\nExiting...',
                level='error',
                indent=0,
                wrap=False,
            )
            sys.exit(1)

    eprint(f'{Font.b}{Font.u}Updates{Font.end}')
    eprint(
        'Getting game updates.\n',
        indent=0,
    )

    # Get the completion status
    completion_status = {'update_finished': False}

    if pathlib.Path(config.cache).joinpath('updates.json').is_file():
        with open(
            pathlib.Path(config.cache).joinpath('updates.json'), encoding='utf-8'
        ) as status_cache:
            try:
                completion_status = json.load(status_cache)
            except Exception:
                pass

    resume: str = ''

    if not config.args.forcerestart and not config.args.writefromcache:
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
        else:
            if 'update_last_run' in completion_status:
                if ['update_last_run']:
                    # Don't resume a partially completed update if more than 6 hours has
                    # passed
                    now = datetime.datetime.now()  # noqa: DTZ005

                    update_last_run = datetime.datetime.strptime(  # noqa: DTZ007
                        completion_status['update_last_run'], '%Y/%m/%d %H:%M'
                    )

                    rd = dateutil.relativedelta.relativedelta(now, update_last_run)

                    input(rd)

                    if rd.hours > 6:
                        eprint(
                            '• Update cache is stale, redownloading update data from scratch.\n',
                            level='warning',
                        )

                        resume = 'r'

            if 'days_to_update' in completion_status and resume != 'r':
                if completion_status['days_to_update'] != config.args.update:
                    eprint(
                        '• The number of days to update is different than the last time you requested an update, redownloading update data from scratch.\n',
                        level='warning',
                    )

                resume = 'r'

    if config.args.writefromcache:
        resume = 'w'

    if resume == 'r' or config.args.forcerestart:
        completion_status = delete_cache('updates', config)
    elif resume == 'q':
        sys.exit()

    if discord_webhook:
        try:
            discord_webhook.send('\u200B')
            discord_webhook.send(f'# Starting updates {get_datetime().strftime("%Y/%m/%d")} ')
            update_message = discord_webhook.send(
                f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Getting updates from MobyGames from the last **{config.args.update}** days...',
                wait=True,
            )
        except Exception as e:
            eprint(f'• Failed to send Discord message: {e}')

    # Start the update requests
    if not completion_status['update_finished']:
        # Set the request offset
        offset: int = 0
        offset_increment: int = 100

        # Figure out the last offset's data that has been cached
        if list(pathlib.Path(config.cache).joinpath('updates/').glob('*.json')):
            offset = (
                max(
                    natsorted(
                        [
                            int(x.stem)
                            for x in pathlib.Path(config.cache).joinpath('updates/').glob('*.json')
                        ]
                    )
                )
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
                request_wait(config)
            else:
                i += 1

            # Make the request for updated games
            game_dict: dict[str, Any] = api_request(
                f'https://api.mobygames.com/v1/games/recent?api_key={config.api_key}&format=normal&age={config.args.update}&offset={offset}&limit={offset_increment}',
                config,
                message=f'• [{get_datetime().strftime("%H:%M:%S")}] Requesting updated titles {offset}-{offset+offset_increment}...',
            ).json()

            # Increment the offset
            offset = offset + offset_increment

            # Break the loop if MobyGames returns an empty response
            if 'games' in game_dict:
                # Strip the sample_screenshots array
                for game in game_dict['games']:
                    try:
                        del game['sample_screenshots']
                    except Exception:
                        pass

                # Break the loop if there's less than 100 titles, as we've reached the end
                eprint(
                    f'• [{get_datetime().strftime("%H:%M:%S")}] Requesting updated titles {offset-offset_increment}-{offset}... done.\n',
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
                pathlib.Path(config.cache).joinpath(f'updates/{offset-offset_increment!s}.json'),
                'w',
                encoding='utf-8',
            ) as platform_request_cache:
                platform_request_cache.write(
                    json.dumps(compress(game_dict), separators=(',', ':'), ensure_ascii=False)
                )

            # Write the completion status
            completion_status['update_last_run'] = get_datetime().strftime("%Y/%m/%d %H:%M")
            completion_status['days_to_update'] = config.args.update

            with open(
                pathlib.Path(config.cache).joinpath('updates.json'), 'w', encoding='utf-8'
            ) as status_cache:
                status_cache.write(json.dumps(completion_status, indent=2, ensure_ascii=False))

            # End the loop if needed
            if end_loop:
                break

    if completion_status['update_finished']:
        if discord_webhook:
            try:
                discord_webhook.edit_message(
                    update_message.id,
                    content=f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Getting updates from MobyGames from the last **{config.args.update}** days... done.',
                )
            except Exception as e:
                eprint(f'• Failed to send Discord message: {e}')

        # Get the platform IDs
        if not pathlib.Path(config.cache).joinpath('platforms.json').is_file():
            get_platforms(config)
            request_wait(config)

        platforms: dict[str, int] = {}

        with open(
            pathlib.Path(config.cache).joinpath('platforms.json'), encoding='utf-8'
        ) as platform_cache:
            platforms = json.loads(platform_cache.read())['platforms']

            platforms = sorted(platforms, key=lambda x: x['platform_id'])

        # Limit the platform updates if a range has been specified
        if config.args.updaterange:
            new_platforms: list[int] = []

            for platform in platforms:
                if platform['platform_id'] in range(
                    config.args.updaterange[0], config.args.updaterange[1] + 1
                ):
                    new_platforms.append(platform)

            if new_platforms:
                platforms = new_platforms

        # Update per platform
        if not config.args.updatecache:
            for platform in platforms:
                # Check the last updated dates for each platform
                last_updated: datetime.datetime | None = None

                if pathlib.Path(config.cache).joinpath(f'{platform["platform_id"]}').is_dir():
                    if (
                        pathlib.Path(config.cache)
                        .joinpath(f'{platform["platform_id"]}/status.json')
                        .is_file()
                    ):
                        with open(
                            pathlib.Path(config.cache).joinpath(
                                f'{platform["platform_id"]}/status.json'
                            ),
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
                    rd = dateutil.relativedelta.relativedelta(get_datetime(), last_updated)

                    if rd.months and rd.days > 21:
                        eprint(
                            f'• It\'s been more than 21 days since the {platform["platform_name"]} platform was updated. It\'s possible that MobyGames hasn\'t updated the platform in this time, but if you\'re running the '
                            'update command manually and haven\'t done so in a long time, you might want to redownload the platform from scratch instead to capture new game details.\n',
                            level='warning',
                        )

                    eprint(
                        f'{Font.b}Updating the {platform["platform_name"]} platform{Font.be} [ID: {platform["platform_id"]}]'
                    )

                    # Read from the update cache
                    updated_games: list[dict[str, Any]] = []

                    for game_file in pathlib.Path(config.cache).joinpath('updates/').glob('*.json'):
                        with open(pathlib.Path(game_file), encoding='utf-8') as update_cache:
                            cache = json.loads(update_cache.read())

                            try:
                                cache = decompress(cache)
                            except Exception:
                                pass

                            updated_games.extend(cache['games'])

                    # Split by platform
                    updated_platform_related_games: list[dict[str, Any]] = []
                    updated_platform_unrelated_games: list[dict[str, Any]] = []

                    for updated_game in updated_games:
                        found_platform: bool = False

                        for platform_release in updated_game['platforms']:
                            if platform_release['platform_id'] == platform['platform_id']:
                                updated_platform_related_games.append(updated_game)
                                found_platform = True

                        if not found_platform:
                            updated_platform_unrelated_games.append(updated_game)

                    if updated_platform_related_games or updated_platform_unrelated_games:
                        # Get all the game IDs for the platform
                        game_ids: set[int] = set()

                        for game_file in (
                            pathlib.Path(config.cache)
                            .joinpath(f'{platform["platform_id"]}/games/')
                            .glob('*.json')
                        ):
                            with open(
                                pathlib.Path(game_file), encoding='utf-8'
                            ) as platform_request_cache:
                                cache = json.loads(platform_request_cache.read())

                                try:
                                    cache = decompress(cache)
                                except Exception:
                                    pass

                                game_ids = game_ids | {x['game_id'] for x in cache['games']}

                        if discord_webhook:
                            original_number_of_games: int = len(game_ids)

                            try:
                                discord_webhook.send('\u200B')
                                discord_webhook.send(f'## {platform["platform_name"]}')
                                applying_updates_message = discord_webhook.send(
                                    f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Applying updates to the **{platform["platform_name"]}** platform [Platform ID: {platform["platform_id"]}]. As of the last update, it had **{original_number_of_games:,}** games.',
                                    wait=True,
                                )
                            except Exception as e:
                                eprint(f'• Failed to send Discord message: {e}')

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

                        # Skip this platform if none of its titles have been updated
                        if not updated_platform_related_games and not removed_game_ids:
                            eprint(
                                f'\nNo updates found for the {platform["platform_name"]} platform, skipping...\n',
                                level='warning',
                                wrap=False,
                            )
                            if discord_webhook:
                                try:
                                    discord_webhook.edit_message(
                                        applying_updates_message.id,
                                        content=f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] ~~Applying updates to the **{platform["platform_name"]}** platform [Platform ID: {platform["platform_id"]}]. As of the last update, it had **{original_number_of_games:,}** games.~~ _No updates found, skipping._',
                                    )
                                except Exception as e:
                                    eprint(f'• Failed to send Discord message: {e}')
                            continue

                        if discord_webhook:
                            try:
                                update_message = discord_webhook.send(
                                    f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Adding or updating **{len(updated_platform_related_games)}** games in the **{platform["platform_name"]}** platform cache, and deleting **{len(removed_game_ids)}** games...',
                                    wait=True,
                                )
                            except Exception as e:
                                eprint(f'• Failed to send Discord message: {e}')

                        # Recreate the cached files in the games folder
                        added_game_ids: set[int] = set()
                        file_contents: list[str] = []
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
                                            pathlib.Path(config.cache).joinpath(
                                                f'{platform["platform_id"]}/games/{100*file_count}.json'
                                            ),
                                            encoding='utf-8',
                                        ) as platform_request_cache:
                                            cache = json.loads(platform_request_cache.read())

                                            try:
                                                cache = decompress(cache)
                                            except Exception:
                                                pass

                                    # Get the last ID in the cache file, and if we've
                                    # exceeded it, don't check this file again
                                    last_id: int = max([x['game_id'] for x in cache['games']])

                                    # Grab the game ID entry from the cache file
                                    file_contents.extend(
                                        [x for x in cache['games'] if x['game_id'] == game_id]
                                    )
                                    added_game_ids.add(game_id)
                                except Exception:
                                    pass

                            # Check if modulo 100 == 0 or if it's the last game ID, and if
                            # so, write a temporary output file
                            if not len(file_contents) % 100 or game_id == sorted(game_ids)[-1]:
                                json_contents: list[str] = json.dumps(
                                    file_contents, indent=2, ensure_ascii=False
                                ).split('\n')

                                with open(
                                    pathlib.Path(config.cache).joinpath(
                                        f'{platform["platform_id"]}/games/{100*file_count}.jsontmp'
                                    ),
                                    'w',
                                    encoding='utf-8',
                                ) as platform_request_cache:
                                    cache_file_write: list[str] = []
                                    cache_file_write.append('{\n  "games": ')
                                    for i, line in enumerate(json_contents):
                                        if i == 0:
                                            cache_file_write.append(f'{line}\n')
                                        elif i == len(json_contents) - 1:
                                            cache_file_write.append(f'  {line}')
                                        else:
                                            cache_file_write.append(f'  {line}\n')
                                    cache_file_write.append('  \n}')

                                    platform_request_cache.write(
                                        json.dumps(
                                            compress(json.loads(''.join(cache_file_write))),
                                            separators=(',', ':'),
                                            ensure_ascii=False,
                                        )
                                    )

                                file_contents = []
                                file_count += 1

                        # Rename temporary files to overwrite the existing cache files
                        for game_file in natsorted(
                            pathlib.Path(config.cache)
                            .joinpath(f'{platform["platform_id"]}/games/')
                            .glob('*.jsontmp')
                        ):
                            game_file.replace(
                                pathlib.Path(
                                    f'{pathlib.Path(game_file.parent).joinpath(game_file.stem)}.json'
                                )
                            )

                        # Update cache file
                        completion_status: dict[str, bool] = {
                            'stage_1_finished': True,
                            'stage_2_finished': True,
                            'last_updated': get_datetime().strftime("%Y/%m/%d"),
                        }

                        with open(
                            pathlib.Path(config.cache).joinpath(
                                f'{platform["platform_id"]}/status.json'
                            ),
                            'w',
                            encoding='utf-8',
                        ) as status_cache:
                            status_cache.write(
                                json.dumps(completion_status, indent=2, ensure_ascii=False)
                            )

                        eprint('• Updating cache files... done.', overwrite=True)

                        if discord_webhook:
                            try:
                                discord_webhook.edit_message(
                                    update_message.id,
                                    content=f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Adding or updating **{len(updated_platform_related_games)}** games in the **{platform["platform_name"]}** platform cache, and deleting **{len(removed_game_ids)}** games... done.',
                                )
                                if len(removed_game_ids) / original_number_of_games > 0.05:
                                    discord_webhook.send(
                                        f'## ⚠️ WARNING: More than 5% of titles have been removed from the database for the **{platform["platform_name"]}** platform, check that this is valid ⚠️'
                                    )
                            except Exception as e:
                                eprint(f'• Failed to send Discord message: {e}')

                        # Download new and updated game details, and remove game details
                        # files for those games that have been removed from the platform
                        if updated_platform_related_games:
                            eprint(
                                f'• {len(updated_platform_related_games)} game IDs changed or were added: {", ".join([str(x["game_id"]) for x in sorted(updated_platform_related_games, key=lambda x: x["game_id"])])}'
                            )
                            eprint('• Downloading updated game details.')

                            if discord_webhook:
                                changed_game_ids: list[str] = [
                                    f'[{x["game_id"]!s}](https://www.mobygames.com/game/{x["game_id"]!s}/)'
                                    for x in sorted(
                                        updated_platform_related_games, key=lambda x: x["game_id"]
                                    )
                                ]
                                try:
                                    discord_webhook.send(
                                        f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Added or updated the following game IDs:'
                                    )
                                except Exception as e:
                                    eprint(f'• Failed to send Discord message: {e}')

                                game_id_chunk: int = 10

                                # TODO: This should be executed async, as big game lists can really hold up the code
                                for i in range(0, len(changed_game_ids), game_id_chunk):
                                    try:
                                        discord_webhook.send(
                                            f'{", ".join(changed_game_ids[i:i+game_id_chunk])}',
                                            suppress_embeds=True,
                                            wait=True,
                                        )
                                    except Exception as e:
                                        eprint(f'• Failed to send Discord message: {e}')

                            updated_platform_games_sorted = sorted(
                                updated_platform_related_games, key=lambda x: x['game_id']
                            )
                            game_iterator = 0

                            # Start downloading game details part way through the update list if the right argument is passed
                            if config.args.gameupdateindex:
                                updated_platform_games_sorted = sorted(
                                    updated_platform_related_games, key=lambda x: x['game_id']
                                )[config.args.gameupdateindex - 1 :]
                                game_iterator = config.args.gameupdateindex - 1

                            # Get the updated game details
                            config.time_estimate_given = False

                            for updated_platform_related_game in updated_platform_games_sorted:
                                game_id = updated_platform_related_game['game_id']
                                game_title = updated_platform_related_game['title']
                                game_count = len(updated_platform_related_games)

                                if not config.time_estimate_given:
                                    eta_string = time_estimate(config, game_count, game_iterator)

                                    eprint(
                                        f'{Font.heading}• Estimated completion time: {eta_string} (doesn\'t account for retries or response delays){Font.end}',
                                        wrap=False,
                                    )

                                    if discord_webhook:
                                        try:
                                            discord_webhook.send(
                                                f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Downloading extended details for individual games, estimated completion is in {eta_string} (doesn\'t account for retries or response delays)...'
                                            )
                                        except Exception as e:
                                            eprint(f'• Failed to send Discord message: {e}')

                                    config.time_estimate_given = True

                                game_iterator += 1

                                game_response: requests.models.Response = api_request(
                                    f'https://api.mobygames.com/v1/games/{game_id}/platforms/{platform["platform_id"]}?api_key={config.api_key}',
                                    config,
                                    message=f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Requesting details for {game_title} [ID: {game_id}] ({game_iterator:,}/{game_count:,})...',
                                    type='game-details',
                                )

                                if game_response.status_code == 404:
                                    request_wait(config)
                                    continue

                                game_details: dict[str, Any] = game_response.json()

                                with open(
                                    pathlib.Path(config.cache).joinpath(
                                        f'{platform["platform_id"]}/games-details/{game_id}.json'
                                    ),
                                    'w',
                                    encoding='utf-8',
                                ) as game_details_cache:
                                    game_details_cache.write(
                                        json.dumps(
                                            compress(game_details),
                                            separators=(',', ':'),
                                            ensure_ascii=False,
                                        )
                                    )

                                eprint(
                                    f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Requesting details for {game_title} [ID: {game_id}] ({game_iterator:,}/{game_count:,})... done.\n',
                                    overwrite=True,
                                    wrap=False,
                                )

                                request_wait(config)

                            if discord_webhook:
                                try:
                                    discord_webhook.send(
                                        f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Finished downloading extended game details for **{platform["platform_name"]}**.'
                                    )
                                except Exception as e:
                                    eprint(f'• Failed to send Discord message: {e}')

                        if removed_game_ids:
                            eprint(
                                f'• {len(removed_game_ids)} game IDs were removed: {", ".join([str(x) for x in sorted(removed_game_ids)])}'
                            )
                            eprint('• Deleting removed games from the cache...')
                            for game_id in removed_game_ids:
                                if (
                                    pathlib.Path(config.cache)
                                    .joinpath(
                                        f'{platform["platform_id"]}/games-details/{game_id}.json'
                                    )
                                    .is_file()
                                ):
                                    pathlib.Path(config.cache).joinpath(
                                        f'{platform["platform_id"]}/games-details/{game_id}.json'
                                    ).unlink()

                            eprint(
                                '• Deleting removed games from the cache... done', overwrite=True
                            )

                            if discord_webhook:
                                try:
                                    removed_game_ids_message: list[str] = [
                                        f'[{x!s}](https://www.mobygames.com/game/{x}/)'
                                        for x in sorted(removed_game_ids)
                                    ]
                                    discord_webhook.send(
                                        f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Deleted the following game IDs:'
                                    )
                                    game_id_chunk = 10
                                    for i in range(0, len(removed_game_ids_message), game_id_chunk):
                                        discord_webhook.send(
                                            f'{", ".join(removed_game_ids_message[i:i+game_id_chunk])}',
                                            suppress_embeds=True,
                                            wait=True,
                                        )
                                except Exception as e:
                                    eprint(f'• Failed to send Discord message: {e}')

                        # Write out the files for the platform
                        if discord_webhook:
                            try:
                                output_message = discord_webhook.send(
                                    f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Generating output files...',
                                    wait=True,
                                )
                            except Exception as e:
                                eprint(f'• Failed to send Discord message: {e}')

                        write_output_files(
                            config, platform['platform_id'], platform['platform_name']
                        )

                        if discord_webhook:
                            try:
                                discord_webhook.edit_message(
                                    output_message.id,
                                    content=f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] Generating output files... done.',
                                )
                                discord_webhook.send(
                                    content=f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] The **{platform["platform_name"]}** platform [Platform ID: {platform["platform_id"]}] now has **{len(game_ids):,}** games.'
                                )
                                discord_webhook.send(
                                    f'• [{get_datetime().strftime("%Y/%m/%d %H:%M:%S")}] {platform['platform_name']} update completed'
                                )
                            except Exception as e:
                                eprint(f'• Failed to send Discord message: {e}')

                    else:
                        eprint('• No games needed to be updated.')
    if discord_webhook:
        discord_webhook.send('\u200B')
        discord_webhook.send('### Updates complete')


def time_estimate(config, game_count, game_iterator) -> str:
    eta: datetime.timedelta = datetime.timedelta(
        seconds=int((game_count - game_iterator) * (config.rate_limit + 1.6))
    )

    if not eta:
        eta: datetime.timedelta = datetime.timedelta(seconds=int((1) * (config.rate_limit + 1.6)))

    eta_list: list[str] = []
    eta_string: str = ''

    if eta.days:
        eta_list.append(f'{eta.days!s} days')
    if int(str(eta)[-8:-6]) != 0:
        eta_hours: str = str(eta)[-8:-6]

        if eta_hours.startswith('0'):
            eta_hours = eta_hours[1:]

        eta_list.append(f'{eta_hours} hours')
    if int(str(eta)[-5:-3]) != 0:
        eta_minutes: str = str(eta)[-5:-3]

        if eta_minutes.startswith('0'):
            eta_minutes = eta_minutes[1:]

        eta_list.append(f'{eta_minutes} minutes')
    if int(str(eta)[-2:]) != 0:
        eta_seconds: str = str(eta)[-2:]

        if eta_seconds.startswith('0'):
            eta_seconds = eta_seconds[1:]

        eta_list.append(f'{eta_seconds} seconds')

    if len(eta_list) > 2:
        eta_list[-1] = f'and {eta_list[-1]}'

        eta_string = ', '.join(eta_list)
    elif len(eta_list) == 2:
        eta_list[-1] = f' and {eta_list[-1]}'
        eta_string = ''.join(eta_list)
    else:
        eta_string = ''.join(eta_list)

    return eta_string


def write_output_files(config: Config, platform_id: int, platform_name: str) -> None:
    """
    Writes files based on downloaded MobyGames data in multiple formats.

    Args:
        config (Config): The MobyDump config object instance.
        platform_id (int): The MobyGames platform ID.
        platform_name (str): The MobyGames platform name.
        update (bool): Whether an update is being run.
    """
    compress_files: list[pathlib.Path] = []
    file_platform_name: str = replace_invalid_characters(platform_name)

    # Create the output path
    if config.output_path:
        pathlib.Path(config.output_path).mkdir(parents=True, exist_ok=True)

    # Don't write files
    if config.output_file_type == 0:
        eprint(
            '• Finished processing titles.',
            wrap=False,
        )

    # Write the output file in JSON
    if config.output_file_type == 2 or config.output_file_type == 3:
        eprint('• Finished processing titles. Writing JSON output file...', indent=0, wrap=False)

        # Enrich games with individual game details, and write to the JSON file
        output_file: str = f'{config.prefix}{file_platform_name}.json'
        output_file = pathlib.Path(config.output_path).joinpath(output_file)
        if output_file.is_file():
            pathlib.Path(output_file).unlink()

        json_file_contents: list[str] = ['{\n  "games": [\n']

        # Guard against duplicates, which can possibly be in cache files due to timing
        # issues between requests
        game_id_check: set[int] = set()

        for game_file in (
            pathlib.Path(config.cache).joinpath(f'{platform_id}/games/').glob('*.json')
        ):
            with open(pathlib.Path(game_file), encoding='utf-8') as platform_request_cache:
                cache: dict[str, Any] = json.loads(platform_request_cache.read())

                try:
                    cache = decompress(cache)
                except Exception:
                    pass

                # Add the game contents to the file
                for game in cache['games']:
                    if game['game_id'] not in game_id_check:
                        game_id_check.add(game['game_id'])

                        if (
                            pathlib.Path(config.cache)
                            .joinpath(f'{platform_id}/games-details/{game['game_id']}.json')
                            .is_file()
                        ):
                            with open(
                                pathlib.Path(config.cache).joinpath(
                                    f'{platform_id}/games-details/{game['game_id']}.json'
                                ),
                                encoding='utf-8',
                            ) as game_details_cache:
                                loaded_game_details: dict[str, Any] = json.load(game_details_cache)

                                try:
                                    loaded_game_details = decompress(loaded_game_details)
                                except Exception:
                                    pass

                                # Add the game details keys to the game
                                for key, values in loaded_game_details.items():
                                    game[key] = values

                                # Sort alphabetically by key
                                game = dict(sorted(game.items()))

                                # Move game ID and title to the top
                                game = {'game_id': game.pop('game_id'), **game}
                                game = {'title': game.pop('title'), **game}

                                with open(
                                    pathlib.Path(output_file), 'a', encoding='utf-8-sig'
                                ) as file:
                                    game_json: str = (
                                        f'{json.dumps(game, indent=2, ensure_ascii=False)},'
                                    )

                                    for line in game_json.split('\n'):
                                        json_file_contents.append(f'    {line}\n')

        # Write the file
        json_file_contents = json_file_contents[:-1]
        json_file_contents.append('    }\n  ]\n}\n')
        with open(pathlib.Path(output_file), 'a', encoding='utf-8-sig') as file:
            file.write(''.join(json_file_contents))

        compress_files.append(pathlib.Path(output_file))

        eprint(
            '• Finished processing titles. Writing JSON output file... done.',
            overwrite=True,
            wrap=False,
        )

    # Write the output files as delimiter-separated value files
    if config.output_file_type == 1 or config.output_file_type == 3:
        # Organize the data into separate tables for output, as Access can't
        # handle more than 255 columns of data, and the API returns data of
        # different shapes
        eprint(
            '• Organizing game data...',
            indent=0,
        )

        game_ids: list[int] = []
        games_dataframe: pd.DataFrame = pd.DataFrame()

        for game_file in (
            pathlib.Path(config.cache).joinpath(f'{platform_id}/games/').glob('*.json')
        ):
            with open(pathlib.Path(game_file), encoding='utf-8') as platform_request_cache:
                cache = json.loads(platform_request_cache.read())

                try:
                    cache = decompress(cache)
                except Exception:
                    pass

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

        # Remove lines with no alternate title
        if 'title' in games_alternate_titles_dataframe:
            games_alternate_titles_dataframe['title'] = games_alternate_titles_dataframe[
                'title'
            ].replace('', np.nan)
            games_alternate_titles_dataframe.dropna(subset=['title'], inplace=True)

        # Split out genres into their own dataframe
        genres_dataframe = games_dataframe.filter(['genres', 'game_id'])
        games_dataframe.pop('genres')

        # Expand genres, add the game ID, and convert some columns to integers
        genres_dataframe = genres_dataframe.explode('genres', ignore_index=True)

        exploded_genres = pd.json_normalize(genres_dataframe['genres'])  # type: ignore
        exploded_genres['game_id'] = genres_dataframe['game_id']

        genres_dataframe = exploded_genres
        genres_dataframe.insert(0, 'game_id', genres_dataframe.pop('game_id'))

        # Remove lines with no genre category
        if 'genre_category' in genres_dataframe:
            genres_dataframe['genre_category'] = genres_dataframe['genre_category'].replace(
                '', np.nan
            )
            genres_dataframe.dropna(subset=['genre_category'], inplace=True)

        genres_dataframe['genre_category_id'] = (
            genres_dataframe['genre_category_id'].fillna(0).astype(int)
        )
        genres_dataframe['genre_id'] = genres_dataframe['genre_id'].fillna(0).astype(int)

        # Get individual game details data
        games_details: list[dict[str, Any]] = []

        for game_id in game_ids:
            if (
                pathlib.Path(config.cache)
                .joinpath(f'{platform_id}/games-details/{game_id}.json')
                .is_file()
            ):
                try:
                    with open(
                        pathlib.Path(config.cache).joinpath(
                            f'{platform_id}/games-details/{game_id}.json'
                        ),
                        encoding='utf-8',
                    ) as games_details_cache:

                        game_detail = decompress(json.load(games_details_cache))

                        games_details.append(game_detail)
                except Exception:
                    # Grab the game data again if it's corrupt
                    game_response: requests.models.Response = api_request(
                        f'https://api.mobygames.com/v1/games/{game_id}/platforms/{platform_id}?api_key={config.api_key}',
                        config,
                        message=f'• Re-requesting details for game ID: {game_id}, as it seems to be corrupt...',
                        type='game-details',
                    )

                    # Delete the file if a 404 is received
                    if game_response.status_code == 404:
                        pathlib.Path(config.cache).joinpath(
                            f'{platform_id}/games-details/{game_id}.json'
                        ).unlink()
                        continue

                    game_details: dict[str, Any] = game_response.json()

                    with open(
                        pathlib.Path(config.cache).joinpath(
                            f'{platform_id}/games-details/{game_id}.json'
                        ),
                        'w',
                        encoding='utf-8',
                    ) as game_details_cache:
                        game_details_cache.write(
                            json.dumps(
                                compress(game_details),
                                separators=(',', ':'),
                                ensure_ascii=False,
                            )
                        )

                    request_wait(config)

                    eprint(
                        f'• Re-requesting details for game ID: {game_id}, as it seems to be corrupt... done.',
                        overwrite=True,
                    )

                    games_details.append(game_details)

        games_details = sorted(games_details, key=lambda x: x['game_id'])

        if not games_details:
            eprint(
                f'\nLooks like {platform_name} has extended game details missing, you might have downloaded with '
                '--skipdetails. You need to redownload this platform without --skipdetails to continue. Exiting...',
                level='warning',
            )
            sys.exit()

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
        eprint(
            '• Finished processing titles. Writing delimiter-separated value output files...',
            indent=0,
            wrap=False,
        )

        def write_file(dataframe: pd.DataFrame, output_file: str) -> None:
            # Sanitize the dataframe
            dataframe = sanitize_dataframes(dataframe)

            # Remove duplicates where appropriate, which can possibly be in cache files
            # due to timing issues between requests
            if dataframe.equals(games_dataframe):
                dataframe = dataframe.drop_duplicates(subset=['game_id'])

            # Write to delimited file, using a BOM so Microsoft apps interpret the
            # encoding correctly
            dataframe.to_csv(output_file, index=False, encoding='utf-8-sig', sep=config.delimiter)

            compress_files.append(pathlib.Path(output_file))

        output_path_prefix: pathlib.Path = pathlib.Path(config.output_path).joinpath(
            f'{config.prefix}{file_platform_name}'
        )

        write_file(games_dataframe, f'{output_path_prefix} - (Primary) Games.txt')

        if (
            'title' in games_alternate_titles_dataframe
            and len(games_alternate_titles_dataframe.index) > 0
        ):
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

        eprint(
            '• Finished processing titles. Writing delimiter-separated value output files... done.',
            indent=0,
            overwrite=True,
            wrap=False,
        )

    if config.args.dropbox:
        # Set the zip compression
        compression: int = zipfile.ZIP_DEFLATED
        zf = zipfile.ZipFile(f'{file_platform_name}.zip', mode='w')

        # Add the files
        for file in compress_files:
            try:
                zf.write(file, str(pathlib.Path(file.name)), compress_type=compression)
                file.unlink()
            except Exception:
                pass

        zf.close()

        # Send the zip file to Dropbox
        local_file = pathlib.Path(f'{file_platform_name}.zip')
        dropbox_path = f'/{file_platform_name}.zip'

        # Get a Dropbox access token
        if not config.dropbox_access_token:
            response = get_dropbox_short_lived_token(config)

        # Create an instance of a Dropbox class, which can make requests to the API
        dbx = dropbox.Dropbox(json.loads(response.text)['access_token'])

        # Check that the access token is valid
        try:
            dbx.users_get_current_account()
        except AuthError:
            try:
                eprint(
                    '• Invalid access token. Requesting a new short-lived access token...',
                    level='warning',
                    indent=0,
                    wrap=False,
                )

                response = get_dropbox_short_lived_token(config)
                dbx = dropbox.Dropbox(json.loads(response.text)['access_token'])

                eprint(
                    '• Invalid access token. Requesting a new short-lived access token... done.',
                    indent=0,
                    wrap=False,
                    overwrite=True,
                )

                dbx.users_get_current_account()
            except Exception:
                eprint(
                    '• Invalid access token. Requesting a new short-lived access token didn\'t work.',
                    level='error',
                    indent=0,
                    wrap=False,
                )
                sys.exit(1)

        # Upload the files to Dropbox
        eprint(f'• Uploading {Font.b}{file_platform_name}.zip{Font.be} to Dropbox...')

        with open(local_file, 'rb') as f:
            try:
                dbx.files_upload(f.read(), dropbox_path, mode=WriteMode('overwrite'))
            except ApiError as err:
                # Check that there's enough Dropbox space
                if err.error.is_path() and err.error.get_path().error.is_insufficient_space():
                    eprint(
                        'Can\'t upload file, not enough space in the Dropbox account',
                        level='error',
                        indent=0,
                    )
                    sys.exit(1)
                elif err.user_message_text:
                    eprint(err.user_message_text, level='error', indent=0)
                    sys.exit()
                else:
                    eprint(err, level='error', indent=0)
                    sys.exit()
            except Exception as err:
                eprint(err, level='error', indent=0)
                sys.exit()

        eprint(
            f'• Uploading {Font.b}{file_platform_name}.zip{Font.be} to Dropbox... done.',
            overwrite=True,
        )
        local_file.unlink()

    eprint(f'\n{Font.success}Processing complete{Font.end}\n')
