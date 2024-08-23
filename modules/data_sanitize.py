from __future__ import annotations

import re
import warnings
from typing import Any

import numpy as np
import pandas as pd
from natsort import natsorted

# Ignore Pandas performance warnings for inserts
warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)


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
    column_number = reorder(column_number, 'Game ID', 'game_id')
    column_number = reorder(column_number, 'MobyGames URL', 'moby_url')
    column_number = reorder(column_number, 'First release date', 'first_release_date')
    column_number = reorder(column_number, 'Description', 'description')
    column_number = reorder(column_number, 'Official URL', 'official_url')
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

    # Add the release columns
    release_columns: list[str] = []

    for column in df.columns:
        if column.startswith('Release '):
            release_columns.append(column)

    release_columns = natsorted(release_columns)

    for column in release_columns:
        column_number = reorder(column_number, column.title().replace('_', ' '), column)

    # Sanitize column names
    df.rename(columns=lambda x: x.replace('/', '-'), inplace=True)

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


def restructure_mobygames_response(
    game: dict[str, Any], stage: int, key: str = '', values: Any = {}
) -> dict:
    """
    Extracts and sanitizes data from a MobyGames API response so it's more suitable for a database.

    Args:
        game (dict[str, Any]): A dictionary containing game details from the MobyGames API.

        platform_id (int): The MobyGames platform ID.

        stage (int): What stage is being sanitized.

        key (str): Used only in stage 2.

        values (Any): Used only in stage 2.

    Returns:
        dict: A dictionary containing sanitized game details.
    """
    if stage == 1:
        # Format alternate titles fields
        if 'alternate_titles' in game:

            for alternate_title in game['alternate_titles']:
                # Shorten the field names, as Access limits the line-length when importing
                # files to 65534 characters
                field_name: str = (
                    f'Alt title ({re.sub(' title$', '', alternate_title['description'])})'
                )
                field_name = field_name.replace('Alternate title', 'Alt title')

                game[field_name] = alternate_title['title']

            del game['alternate_titles']

        # Format genre field
        if 'genres' in game:
            if game['genres']:
                for genre in game['genres']:
                    game[f'genres ({genre["genre_category"]})'] = genre["genre_name"]

            del game['genres']

        # Drop unneeded data
        del game['moby_score']
        del game['num_votes']
        del game['platforms']
        del game['sample_cover']
        del game['sample_screenshots']

    if stage == 2:
        # Bring nested data up to the column level and format fields accordingly
        if key == 'attributes':
            attribute_counter: list[Any] = []
            for attributes in values:
                attribute_counter.append(attributes['attribute_category_name'])

                if 'attribute_category_name' in attributes and 'attribute_name' in attributes:
                    game[
                        f'{attributes["attribute_category_name"]} {attribute_counter.count(attributes['attribute_category_name'])}'
                    ] = attributes['attribute_name']
        elif key == 'patches':
            for i, patch in enumerate(values):
                if 'description' in patch:
                    game[f'Patch {i}: Description'] = patch['description']
                if 'release_date' in patch:
                    game[f'Patch {i}: Release date'] = patch['release_date']
        elif key == 'ratings':
            for rating in values:
                game[rating['rating_system_name']] = rating['rating_name']
        elif key == 'releases':
            for i, releases in enumerate(values, start=1):
                for release in releases:
                    if release == 'companies':
                        for company in releases[release]:
                            if 'company_name' in company and 'role' in company:
                                game[f'Release {i}: {company["role"]}'] = company['company_name']
                    elif release == 'countries':
                        for j, country in enumerate(releases[release], start=1):
                            game[f'Release {i}: Country {j}'] = country
                    elif release == 'product_codes':
                        for product_code in releases[release]:
                            for product_code_entry in product_code:
                                game[
                                    f'Release {i}: {product_code_entry}'.title()
                                    .replace('_', '')
                                    .replace(' id', 'ID')
                                ] = product_code[product_code_entry]
                    elif release == 'release_date':
                        game[f'Release {i}: Release date'] = releases[release]
                    else:
                        game[f'Release {i}: {release}'] = releases[release]
        else:
            game[key] = values

    return game
