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
    df = df.replace(r'\t', '    ', regex=True)

    # Normalize curly quotes and replace other problem characters
    df = (
        df.replace(['“', '”'], '"', regex=True)
        .replace(['‘', '’'], '\'', regex=True)  # noqa: RUF001
        .replace(['\u200b', '\u200c'], '', regex=True)
    )

    # Remove null values
    df = df.replace([None, np.nan], '')

    # Normalize problem chacters in column headings
    df.columns = df.columns.str.replace('[.|/]', '_', regex=True)

    return df

