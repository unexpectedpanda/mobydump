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

    # Read the game cache file if it exists
    game_cache: dict[str, Any] = read_game_cache(platform_id)

    # Change the offset if we need to resume
    if game_cache and not completion_status['stage_1_finished']:
        # Get the last key in the cache, and set the offset appropriately
        offset = int(list(game_cache)[-1]) + offset_increment

        eprint(f'• Request was previously interrupted, resuming from offset {offset}')

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
            now = datetime.datetime.now()

            game_dict: dict[str, Any] = api_request(
                f'https://api.mobygames.com/v1/games?api_key={api_key}&platform={platform_id}&offset={offset}&limit={offset_increment}',
                headers,
                message=f'• [{now.strftime("%H:%M:%S")}] Requesting titles {offset}-{offset+offset_increment}...',
            ).json()

            # Add games to the cache, and then process them
            if 'games' in game_dict:
                if game_dict['games']:
                    game_cache[str(offset)] = game_dict

            # Increment the offset
            offset = offset + offset_increment

            # Break the loop if MobyGames returns an empty response or if there's less than 100 titles, as we've
            # reached the end
            if 'games' in game_dict:
                now = datetime.datetime.now()

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
            pathlib.Path(f'cache/{platform_id}/games.json'), 'w', encoding='utf-8'
        ) as platform_request_cache:
            platform_request_cache.write(json.dumps(game_cache, indent=4))

        # Write the completion status
        with open(
            pathlib.Path(f'cache/{platform_id}/status.json'), 'w', encoding='utf-8'
        ) as status_cache:
            status_cache.write(json.dumps(completion_status, indent=4))

        # End the loop if needed
        if end_loop:
            break


def get_game_details(
    games: list[dict[str, Any]],
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

    # Only download game details that haven't been downloaded yet
    for i, game in enumerate(games, start=1):
        if not pathlib.Path(f'cache/{platform_id}/games-platform/{game['game_id']}.json').is_file():
            now = datetime.datetime.now()

            game_details: dict[str, Any] = api_request(
                f'https://api.mobygames.com/v1/games/{game['game_id']}/platforms/{platform_id}?api_key={api_key}',
                headers,
                message=f'• [{now.strftime("%H:%M:%S")}] Requesting details for {game['title']} [ID: {game['game_id']}] ({i:,}/{len(games):,})...',
            ).json()

            with open(
                pathlib.Path(f'cache/{platform_id}/games-platform/{game['game_id']}.json'),
                'w',
                encoding='utf-8',
            ) as game_details_cache:
                game_details_cache.write(json.dumps(game_details, indent=4))

            now = datetime.datetime.now()

            eprint(
                f'• [{now.strftime("%H:%M:%S")}] Requesting details for {game['title']} [ID: {game['game_id']}] ({i:,}/{len(games):,})... done.\n',
                overwrite=True, wrap=False,
            )

            request_wait(rate_limit)

    # Write the completion status
    completion_status['stage_2_finished'] = True

    with open(
        pathlib.Path(f'cache/{platform_id}/status.json'), 'w', encoding='utf-8'
    ) as status_cache:
        status_cache.write(json.dumps(completion_status, indent=4))


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
        platform_cache.write(json.dumps(platforms, indent=4))

    return platforms


def read_game_cache(platform_id: int) -> dict[str, Any]:
    """
    Reads the game cache file.

    Returns:
        dict[str, Any]: The game cache in JSON form.
    """
    game_cache: dict[str, Any] = {}

    if pathlib.Path(f'cache/{platform_id}/games.json').is_file():
        with open(
            pathlib.Path(f'cache/{platform_id}/games.json'), encoding='utf-8'
        ) as platform_request_cache:
            try:
                game_cache = json.load(platform_request_cache)
            except Exception:
                pass

    return game_cache
