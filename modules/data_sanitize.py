import json
import pathlib
import re

import numpy as np
import pandas as pd


def better_platform_name(platform_name: str) -> str:

    better_platform_names: dict[str, str] = {}

    if pathlib.Path('platforms.json').is_file():
        with open(pathlib.Path('platforms.json'), encoding='utf-8') as better_platforms:
            better_platform_names = json.loads(better_platforms.read())

        if platform_name in better_platform_names:
            platform_name = better_platform_names[platform_name]

    return platform_name


def replace_invalid_characters(name: str) -> str:
    r"""
    Removes invalid file / folder name characters from a string.

    Args:
        name (str): A file or folder name.

    Returns:
        str: A string with invalid file characters removed.
    """
    sanitized_characters: tuple[str, ...] = (':', '\\', '/', '<', '>', '"', '|', '?', '*')

    for character in sanitized_characters:
        if character in name:
            if character == ':':
                if re.search('(\\S):\\s', name):
                    name = re.sub('(\\S):\\s', '\\1 - ', name)
                else:
                    name = name.replace(character, '-')
            elif character == '"':
                name = name.replace(character, '\'')
            elif character == '\\':
                name = name.replace(character, '-')
            elif character == '/':
                name = name.replace(character, '-')
            else:
                name = name.replace(character, '-')

    # For strings that start with ., use the fixed width ．instead
    name = re.sub('^\\.', '．', name)  # noqa: RUF001

    return name


def sanitize_dataframes(df: pd.core.frame.DataFrame) -> pd.core.frame.DataFrame:
    """
    Sanitizes problem data in Pandas dataframe records.

    Args:
        df (pd.core.frame.DataFrame): A Pandas dataframe.

    Returns:
        pd.core.frame.DataFrame: A Pandas dataframe with sanitized data.
    """
    pd.set_option('future.no_silent_downcasting', True)

    # Clear out new lines from data
    df = df.replace(r'\n', ' ', regex=True)

    # Clear out tabs from data
    df = df.replace(r'\t', ' ', regex=True)

    # Collapse multiple spaces down to a single space
    if 'description' in df:
        df['description'] = df['description'].str.replace(r'\s{2,}', ' ', regex=True)

    # Remove null values
    df = df.replace([None, np.nan], '')

    # Normalize curly quotes and replace other problem characters
    df = (
        df.replace(['“', '”'], '"', regex=True)
        .replace(['‘', '’'], '\'', regex=True)  # noqa: RUF001
        .replace('×', 'x', regex=True)  # noqa: RUF001
        .replace('…', '...', regex=True)
        .replace(['\u200b', '\u200c'], '', regex=True)
        .replace('\u00a0', ' ', regex=True)
    )

    # Normalize problem chacters in column headings
    df.columns = df.columns.str.replace('[.|/]', '_', regex=True)

    # Because Microsoft Access is terrible with dates, let alone partial dates, create a
    # year column so date queries are easier
    if 'releases_release_date' in df:
        df['releases_release_year'] = df['releases_release_date'].replace(
            '(\\d{4}).*', '\\1', regex=True
        )
        df.insert(
            df.columns.get_loc('releases_release_date') + 1,
            'releases_release_year',
            df.pop('releases_release_year'),
        )

    return df
