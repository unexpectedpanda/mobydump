from __future__ import annotations

import json
import pathlib
from typing import TYPE_CHECKING, Any

from modules.requests import api_request, request_wait
from modules.utils import Font, eprint

if TYPE_CHECKING:
    import argparse


def add_games(
    games_dict: dict[str, Any], games: list[dict[str, Any]], args: argparse.Namespace
) -> list[dict[str, Any]]:
    """
    Reworks game data to be suitable for databases, then adds the game to a list.

    Args:
        games_dict (dict[str, Any]): A response from the MobyGames API containing game details.
        games (list[dict[str, Any]]): A list containing game data from MobyGames.
        args (argparse.Namespace): User input arguments.

    Returns:
        list[dict[str, Any]]: A list containing game data from MobyGames.
    """
    for game_values in games_dict.values():
        for game_value in game_values:
            games.append(game_value)

    return games


def get_games(
    game_cache: dict[str, Any],
    games: list[dict[str, Any]],
    platform_id: int,
    platform_name: str,
    completion_status: dict[str, bool],
    api_key: str,
    rate_limit: int,
    headers: dict[str, str],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    """
    Gets the titles, alternate titles, descriptions, URLs, and genres from MobyGames.

    Args:
        game_cache (dict[str, Any]): The contents of the game cache file.
        games (list[dict[str, Any]]): A list containing game data from MobyGames.
        platform_id (int): The MobyGames platform ID.
        platform_name (str): The MobyGames platform name.
        completion_status (dict[str, bool]): Which stages MobyDump has finished.
        api_key (str): The MobyGames API key.
        rate_limit (int): The rate limit in seconds per request.
        headers (dict[str, str]): The headers to use in the API request.
        args (argparse.Namespace): User input arguments.

    Returns:
        list[dict[str, Any]]: A list containing game data from MobyGames.
    """
    eprint(f'{Font.b}{Font.u}Stage 1{Font.end}')
    eprint(
        'Getting titles, alternate titles, descriptions, URLs, and genres.\n',
        indent=False,
    )
    eprint(f'• Retrieving games from {platform_name}.')

    # Set the request offset
    offset: int = 0
    offset_increment: int = 100

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
            games: dict[str, Any] = api_request(
                f'https://api.mobygames.com/v1/games?api_key={api_key}&platform={platform_id}&offset={offset}&limit={offset_increment}',
                headers,
                message=f'• Requesting titles {offset}-{offset+offset_increment}...',
            ).json()

            # Add games to the cache, and then process them
            if 'games' in games:
                if games['games']:
                    game_cache[str(offset)] = games

            games = add_games(games, games, args)

            # Increment the offset
            offset = offset + offset_increment

            # Break the loop if MobyGames returns an empty response or if there's less than 100 titles, as we've
            # reached the end
            if 'games' in games:
                eprint(
                    f'• Requesting titles {offset-offset_increment}-{offset}... done.\n',
                    overwrite=True,
                )

                if len(games['games']) < 100:
                    completion_status['stage_1_finished'] = True
                    end_loop = True

            elif not games['games']:
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

    # Sort the game list by title, dedupe if necessary
    games = sorted(games, key=lambda d: d['title'])

    return games


def get_game_details(
    games: list[dict[str, Any]],
    platform_id: int,
    completion_status: dict[str, bool],
    api_key: str,
    rate_limit: int,
    headers: dict[str, str],
) -> None:

    eprint(
        f'\n{Font.b}{Font.u}Stage 2{Font.end}\nGetting attributes, patches, ratings, and releases for each game.\n',
        indent=False,
    )

    # Only download game details that haven't been downloaded yet
    for i, game in enumerate(games, start=1):
        if not pathlib.Path(f'cache/{platform_id}/games-platform/{game['game_id']}.json').is_file():
            game_details: dict[str, Any] = api_request(
                f'https://api.mobygames.com/v1/games/{game['game_id']}/platforms/{platform_id}?api_key={api_key}',
                headers,
                message=f'• Requesting details for {game['title']} [ID: {game['game_id']}] ({i:,}/{len(games):,})...',
            ).json()

            with open(
                pathlib.Path(f'cache/{platform_id}/games-platform/{game['game_id']}.json'),
                'w',
                encoding='utf-8',
            ) as game_details_cache:
                game_details_cache.write(json.dumps(game_details, indent=4))

            eprint(
                f'• Requesting details for {game['title']} [ID: {game['game_id']}] ({i:,}/{len(games):,})... done.\n',
                overwrite=True,
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
