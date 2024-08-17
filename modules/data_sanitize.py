from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    import pandas as pd


def reorder_columns(df: pd.core.frame.DataFrame) -> pd.core.frame.DataFrame:
    """
    Takes a Pandas dataframe containing MobyGames game details, and extracts data and
    reorders columns to make the data more accessible in a database.

    Args:
        df (pd.core.frame.DataFrame): A Pandas dataframe.

    Returns:
        pd.core.frame.DataFrame: A Pandas dataframe with rearrange columns.
    """

    def reorder(new_position: int, new_name: str, original_name: str) -> int:
        """
        Reorders columns in a Pandas dataframe. Fails silently if a column isn't found.

        Args:
            new_position (int): The position the column should be inserted in.
            new_name (str): The new name of the column.
            original_name (str): The original name of the column

        Returns:
            int: The last position that was inserted, incremented by 1.
        """
        try:
            df.insert(new_position, new_name, df.pop(original_name))
        except Exception:
            pass

        return new_position + 1

    column_number: int = 0

    column_number = reorder(column_number, 'Title', 'title')
    column_number = reorder(column_number, 'Alternative titles', 'alternate_titles')
    column_number = reorder(column_number, 'Game ID', 'game_id')
    column_number = reorder(column_number, 'MobyGames URL', 'moby_url')
    column_number = reorder(column_number, 'Platforms and release dates', 'platforms')
    column_number = reorder(column_number, 'Description', 'description')
    column_number = reorder(column_number, 'Official URL', 'official_url')
    column_number = reorder(column_number, 'MobyGames score', 'moby_score')
    column_number = reorder(column_number, 'Number of voters', 'num_votes')
    column_number = reorder(column_number, 'Genres (Basic)', 'genres (Basic Genres)')
    column_number = reorder(column_number, 'Genres (Perspective)', 'genres (Perspective)')
    column_number = reorder(column_number, 'Genres (Setting)', 'genres (Setting)')

    # Add the remaining genre columns
    genre_columns: list[str] = []

    for column in df.columns:
        if column.startswith('genre'):
            genre_columns.append(column)

    genre_columns.sort(reverse=True)

    for column in genre_columns:
        column_number = reorder(column_number, column.replace('genres', 'Genres'), column)

    # Add sample cover details
    column_number = reorder(column_number, 'Sample cover image', 'Sample cover image')
    column_number = reorder(column_number, 'Sample cover width', 'Sample cover width')
    column_number = reorder(column_number, 'Sample cover height', 'Sample cover height')
    column_number = reorder(column_number, 'Sample cover platforms', 'Sample cover platforms')
    column_number = reorder(
        column_number, 'Sample cover thumbnail image', 'Sample cover thumbnail image'
    )
    column_number = reorder(column_number, 'Sample screenshots', 'Sample screenshots')

    # Add screenshots
    screenshot_columns: list[str] = []

    for column in df.columns:
        if column.startswith('Screenshot'):
            screenshot_columns.append(column)

    highest_screenshot_number: int = max(
        [int(''.join(filter(str.isdigit, x))) for x in screenshot_columns]
    )

    for i in range(1, highest_screenshot_number + 1):
        column_number = reorder(column_number, f'Screenshot {i} image', f'Screenshot {i} image')
        column_number = reorder(column_number, f'Screenshot {i} width', f'Screenshot {i} width')
        column_number = reorder(column_number, f'Screenshot {i} height', f'Screenshot {i} height')
        column_number = reorder(column_number, f'Screenshot {i} caption', f'Screenshot {i} caption')
        column_number = reorder(
            column_number, f'Screenshot {i} thumbnail image', f'Screenshot {i} thumbnail_image'
        )

    return df


def sanitize_columns(df: pd.core.frame.DataFrame) -> pd.core.frame.DataFrame:
    """
    Sanitizes problem data in Pandas dataframe columns.

    Args:
        df (pd.core.frame.DataFrame): A Pandas dataframe.

    Returns:
        pd.core.frame.DataFrame: A Pandas dataframe with sanitized data.
    """
    # Clear out new lines from data
    df = df.replace(r'\n', ' ', regex=True)

    # Clear out tabs from data
    df = df.replace(r'\t', '    ', regex=True)

    # Normalize curly quotes and replace other problem characters
    df = (
        df.replace(['“', '”'], '"', regex=True)
        .replace(['‘', '’'], '\'', regex=True)  # noqa: RUF001
        .replace(['\u200b', '\u200c'], '', regex=True)
    )

    # Remove null values
    df = df.replace([None, np.nan], '')

    return df


def sanitize_mobygames_response(game: dict[str, Any]) -> dict:
    """
    Extracts and sanitizes data from a MobyGames API response so it's more suitable for a database.

    Args:
        game (dict[str, Any]): A dictionary containing game details from the MobyGames API.

    Returns:
        dict: A dictionary containing sanitized game details.
    """
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

        del game['genres']

    # Format platforms field
    if 'platforms' in game:
        if game['platforms']:
            game_platforms: list[str] = []

            for platforms in game['platforms']:
                game_platforms.append(
                    f'{platforms["platform_name"]} ({platforms["first_release_date"]})'
                )

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

        del game['sample_cover']

    if 'sample_screenshots' in game:
        if game['sample_screenshots']:
            for i, screenshot in enumerate(game['sample_screenshots'], start=1):
                for key, value in screenshot.items():
                    game[f'Screenshot {i} {key}'] = value

        del [game['sample_screenshots']]

    return game
