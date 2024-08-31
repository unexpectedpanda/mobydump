from __future__ import annotations

import datetime
import json
import pathlib
from typing import Any

from modules.requests import api_request, request_wait
from modules.utils import Font, eprint


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


def delete_cache(platform_id: int) -> dict[str, bool]:
    """
    Deletes the local cache for a downloaded platform.

    Args:
        platform_id (int): The MobyGames platform ID to delete downloaded data for.

    Returns:
        dict[str, bool]: A reset completion status.
    """
    # Delete the game cache file
    for game_file in pathlib.Path(f'cache/{platform_id}/games/').glob('*.json'):
        game_file.unlink()

    # Delete the game details files
    for game_details_file in pathlib.Path(f'cache/{platform_id}/games-details/').glob('*.json'):
        game_details_file.unlink()

    # Rewrite the status file
    completion_status = {
        'stage_1_finished': False,
        'stage_2_finished': False,
    }

    with open(
        pathlib.Path(f'cache/{platform_id}/status.json'), 'w', encoding='utf-8'
    ) as status_cache:
        status_cache.write(json.dumps(completion_status, indent=2))

    return completion_status


def get_games(
    platform_id: int,
    platform_name: str,
    completion_status: dict[str, bool],
    api_key: str,
    rate_limit: int,
    headers: dict[str, str],
) -> None:
    """
    Gets the titles, alternate titles, descriptions, URLs, and genres from MobyGames.

    Args:
        platform_id (int): The MobyGames platform ID.
        platform_name (str): The MobyGames platform name.
        completion_status (dict[str, bool]): Which stages MobyDump has finished.
        api_key (str): The MobyGames API key.
        rate_limit (int): The rate limit in seconds per request.
        headers (dict[str, str]): The headers to use in the API request.
    """
    now: datetime.datetime

    eprint(f'{Font.b}{Font.u}Stage 1{Font.end}')
    eprint(
        'Getting titles, alternate titles, descriptions, URLs, and genres.\n',
        indent=False,
    )
    eprint(f'• Retrieving games from {platform_name}.')

    # Set the request offset
    offset: int = 0
    offset_increment: int = 100

    # Figure out the last offset's data that has been cached
    for game_file in pathlib.Path(f'cache/{platform_id}/games/').glob('*.json'):
        offset = int(game_file.stem) + offset_increment

        eprint(f'• Requests were previously interrupted, resuming from offset {offset}')

    # Get all the response pages for a platform, and add the games to a list
    i: int = 0

    while True:
        # Wait for the rate limit after the first request
        if i > 0:
            request_wait(rate_limit)
        else:
            i += 1

        end_loop: bool = False

        if not completion_status['stage_1_finished']:
            # Make the request for the platform's games
            now = (
                datetime.datetime.now(tz=datetime.timezone.utc)
                .replace(tzinfo=datetime.timezone.utc)
                .astimezone(tz=None)
            )

            game_dict: dict[str, Any] = api_request(
                f'https://api.mobygames.com/v1/games?api_key={api_key}&platform={platform_id}&offset={offset}&limit={offset_increment}',
                headers,
                message=f'• [{now.strftime("%H:%M:%S")}] Requesting titles {offset}-{offset+offset_increment}...',
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
                    f'• [{now.strftime("%H:%M:%S")}] Requesting titles {offset-offset_increment}-{offset}... done.\n',
                    overwrite=True,
                )

                if len(game_dict['games']) < 100:
                    completion_status['stage_1_finished'] = True
                    end_loop = True

            elif not game_dict['games']:
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
            platform_request_cache.write(json.dumps(game_dict, indent=2, ensure_ascii=False))

        # Write the completion status
        with open(
            pathlib.Path(f'cache/{platform_id}/status.json'), 'w', encoding='utf-8'
        ) as status_cache:
            status_cache.write(json.dumps(completion_status, indent=2))

        # End the loop if needed
        if end_loop:
            break


def get_game_details(
    platform_id: int,
    completion_status: dict[str, bool],
    api_key: str,
    rate_limit: int,
    headers: dict[str, str],
) -> None:
    """
    Gets the attributes, patches, ratings, and releases for each game from MobyGames.

    Args:
        games (list[dict[str, Any]]): A list containing game data from MobyGames.
        platform_id (int): The MobyGames platform ID.
        completion_status (dict[str, bool]): Which stages MobyDump has finished.
        api_key (str): The MobyGames API key.
        rate_limit (int): The rate limit in seconds per request.
        headers (dict[str, str]): The headers to use in the API request.
    """
    now: datetime.datetime

    eprint(
        f'\n{Font.b}{Font.u}Stage 2{Font.end}\nGetting attributes, patches, ratings, and releases for each game.\n',
        indent=False,
    )

    # Show a resume message if needed
    if list(pathlib.Path(f'cache/{platform_id}/games-details/').glob('*.json')):
        eprint('• Requests were previously interrupted, resuming...')

    # Get the game count
    files: list[pathlib.Path] = list(pathlib.Path(f'cache/{platform_id}/games/').glob('*.json'))
    file_count: int = len(files)
    game_count: int = file_count * 100 - 100

    for i, game_file in enumerate(files):
        if i + 1 == file_count:
            with open(pathlib.Path(game_file), encoding='utf-8') as platform_request_cache:
                cache: dict[str, Any] = json.loads(platform_request_cache.read())

                game_count = game_count + len(cache['games'])

    game_iterator: int = 0

    for game_file in pathlib.Path(f'cache/{platform_id}/games/').glob('*.json'):

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
                    f'https://api.mobygames.com/v1/games/{game_id}/platforms/{platform_id}?api_key={api_key}',
                    headers,
                    message=f'• [{now.strftime("%Y/%m/%d %H:%M:%S")}] Requesting details for {game_title} [ID: {game_id}] ({game_iterator:,}/{game_count:,})...',
                ).json()

                with open(
                    pathlib.Path(f'cache/{platform_id}/games-details/{game_id}.json'),
                    'w',
                    encoding='utf-8',
                ) as game_details_cache:
                    game_details_cache.write(json.dumps(game_details, indent=2, ensure_ascii=False))

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

                request_wait(rate_limit)

    # Write the completion status
    completion_status['stage_2_finished'] = True

    with open(
        pathlib.Path(f'cache/{platform_id}/status.json'), 'w', encoding='utf-8'
    ) as status_cache:
        status_cache.write(json.dumps(completion_status, indent=2))


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


def get_platforms(api_key, headers) -> dict[str, list[dict[str, str | int]]]:
    """
    Make the platform request, and write the results to a JSON file for an offline
    cache.

    api_key (str): The MobyGames API key.
    headers (dict[str, str]): The headers to use in the API request.

    Returns:
        dict[str, list[dict[str, str | int]]]: The contents of the response, in JSON form.
    """
    platforms: dict[str, list[dict[str, str | int]]] = api_request(
        f'https://api.mobygames.com/v1/platforms?api_key={api_key}',
        headers,
        message='• Retrieving platforms...',
    ).json()

    eprint('• Retrieving platforms... done.', overwrite=True)

    # Store the response in a file
    if not pathlib.Path('cache').is_dir():
        pathlib.Path('cache').mkdir(parents=True, exist_ok=True)

    with open(pathlib.Path('cache/platforms.json'), 'w', encoding='utf-8') as platform_cache:
        platform_cache.write(json.dumps(platforms, indent=2, ensure_ascii=False))

    return platforms
