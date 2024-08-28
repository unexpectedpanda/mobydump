import numpy as np
import pandas as pd


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

    # Normalize curly quotes and replace other problem characters
    df = (
        df.replace(['“', '”'], '"', regex=True)
        .replace(['‘', '’'], '\'', regex=True)  # noqa: RUF001
        .replace(['\u200b', '\u200c'], '', regex=True)
        .replace('\u00a0', ' ', regex=True)
    )

    # Remove null values
    df = df.replace([None, np.nan], '')

    # Normalize problem chacters in column headings
    df.columns = df.columns.str.replace('[.|/]', '_', regex=True)

    return df
