import warnings
from copy import deepcopy
from typing import Any

import numpy as np
import pandas as pd
from natsort import natsorted

# Ignore Pandas performance warnings for inserts
warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)

def json_to_dataframe(data_in: dict[str, Any]) -> list[Any]:
    """
    Converts nested data to a flattened list.

    From: https://stackoverflow.com/questions/41180960/convert-nested-json-to-csv-file-in-python

    Args:
        data_in (dict[str, Any]): JSON data in dictionary form.

    Returns:
        A flattened list.
    """
    def cross_join(left: list[dict[str, Any]], right: str):
        """
        Uses the cartesian product of a nested dictionary to flatten it.

        Args:
            left (list[dict[str, Any]]): _description_
            right (str): The previous key in the hierarchy, so the column can be named
                after it. For example, `key_subkey`.

        Returns:
            list[Any]: The flattened dictionary in list form.
        """
        new_rows = [] if right else left
        for left_row in left:
            for right_row in right:
                temp_row = deepcopy(left_row)
                for key, value in right_row.items():
                    temp_row[key] = value
                new_rows.append(deepcopy(temp_row))

            return new_rows

    def flatten_json(data: Any, prev_heading: str='') -> list[Any]:
        """
        Flattens a nested dictionary.

        Args:
            data (Any): Any valid JSON-like data-structure.
            prev_heading (str, optional): The previous key in the hierarchy. Defaults to
                ''.

        Returns:
            list[Any]: A flattened data structure, in list form.
        """
        if isinstance(data, dict):
            rows = [{}]
            for key, value in data.items():
                rows = cross_join(rows, flatten_json(value, f'{prev_heading}_{key}'))
        elif isinstance(data, list):
            rows = []
            for item in data:
                [rows.append(elem) for elem in flatten_list(flatten_json(item, prev_heading))]
        else:
            rows = [{prev_heading[1:]: data}]

        return rows

    def flatten_list(data):
        """
        Flattens nested lists in a dictionary.

        Args:
            data (list[Any]): The list to flatten.

        Yields:
            Any: The flattened list.
        """
        for elem in data:
            if isinstance(elem, list):
                yield from flatten_list(elem)
            else:
                yield elem

    return flatten_json(data_in)


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


def restructure_mobygames_response(game: dict[str, Any]) -> dict:
    """
    Extracts and sanitizes data from a MobyGames API response so it's more suitable for a database.

    Args:
        game (dict[str, Any]): A dictionary containing game details from the MobyGames API.

    Returns:
        dict: A dictionary containing sanitized game details.
    """
    # Format alternate titles fields
    if 'alternate_titles' in game:

        for alternate_title in game['alternate_titles']:
            game[f'alt titles|{alternate_title["description"]}'] = alternate_title['title']

        del game['alternate_titles']

    # Format genre field
    if 'genres' in game:
        if game['genres']:
            for genre in game['genres']:
                game[f'genres|{genre["genre_category"]}'] = genre["genre_name"]

        del game['genres']

    return game



def split_game_details(game_id: int, game_details: dict[str, Any], raw_mode: bool):
    """ Splits the game detail response into multiple dataframes, due to the data having
    different sizes.

    Args:
        game_id (int): The MobyGames game ID.

        key (str): The key from the response that's being processed.

        values (Any): The values associated with the key that are being processed.

    Returns:
        _type_: _description_
    """

    attributes: list[dict[str, Any]] = []
    patches: list[dict[str, Any]] = []
    ratings: list[dict[str, Any]] = []
    releases: list[dict[str, Any]] = []

    # Set up keys to ignore
    ignore_keys: list[str] = ['game_id', 'platform_id', 'platform_name']

    for key, values in game_details.items():
        if key not in ignore_keys:
            general_attribute: dict[str, Any] = {'attribute_category_id': -1, 'attribute_category_name': key.capitalize().replace('_', ' '), 'attribute_id': -1, 'attribute_name': values}

            if not raw_mode:
                if key == 'attributes':
                    attributes = json_to_dataframe(values)
                    # attributes_dataframe.insert(0, 'game_id', game_id)
                elif key == 'patches':
                    patches = json_to_dataframe(values)
                    # input(attributes_dataframe.join(patches_dataframe))
                elif key == 'ratings':
                    ratings = json_to_dataframe(values)
                    # for rating in values:
                    #     game_detail[rating['rating_system_name']] = rating['rating_name']
                elif key == 'releases':
                    releases = json_to_dataframe(values)
                #     for releases in values:
                #         for release in releases:
                #             if release == 'companies':
                #                 for company in releases[release]:
                #                     if 'company_name' in company and 'role' in company:
                #                         game_detail[f'{company["role"]}'] = company['company_name']

                #             elif release == 'countries':
                #                 for i, country in enumerate(releases[release], start=1):
                #                     game_detail[f'Country {i}'] = country

                #             elif release == 'product_codes':
                #                 for product_code in releases[release]:
                #                     for product_code_entry in product_code:
                #                         game_detail[
                #                             f'{product_code_entry}'.title()
                #                             .replace('_', '')
                #                             .replace(' id', 'ID')
                #                         ] = product_code[product_code_entry]
                #             elif release == 'release_date':
                #                 game_detail['Release date'] = releases[release]

                #             else:
                #                 game_detail[f'{release}'] = releases[release]

                #         game_releases.append(game_detail)
                else:
                    attributes.append(general_attribute)
            else:
                attributes.append(general_attribute)


    if attributes:
        attributes_dataframe = pd.DataFrame(attributes)
        attributes_dataframe.insert(0, 'game_id', game_id)
        # input(attributes_dataframe)
    if patches:
        patches_dataframe = pd.DataFrame(patches)
        patches_dataframe.insert(0, 'game_id', game_id)
        # input(patches_dataframe)
    if ratings:
        ratings_dataframe = pd.DataFrame(ratings)
        ratings_dataframe.insert(0, 'game_id', game_id)
        # input(ratings_dataframe)
    if releases:
        releases_dataframe = pd.DataFrame(releases)
        releases_dataframe.insert(0, 'game_id', game_id)
        input(releases_dataframe)

    return attributes
