import json
import pathlib
import re
import warnings

import html2text
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning


def better_platform_name(platform_name: str) -> str:

    better_platform_names: dict[str, str] = {}

    if pathlib.Path('platform-names.json').is_file():
        with open(pathlib.Path('platform-names.json'), encoding='utf-8') as better_platforms:
            better_platform_names = json.loads(better_platforms.read())

        if platform_name in better_platform_names:
            platform_name = better_platform_names[platform_name]

    return platform_name


def description_to_markdown(description: str) -> str:
    """
    Convert HTML content in the description to a restricted subset of Markdown,
    which should only keep list formatting.

    Args:
        description (str): The HTML description.

    Returns:
        str: The description in a restricted subset of Markdown.
    """
    # Hide BeautifulSoup warnings that the input looks more like a filename than markup
    warnings.filterwarnings('ignore', category=MarkupResemblesLocatorWarning)

    # Sanitize the HTML content with BeautifulSoup
    html_content = BeautifulSoup(description, 'lxml')

    # Set the options to produce a restricted subset of Markdown
    convert_to_markdown = html2text.HTML2Text()
    convert_to_markdown.unicode_snob = True
    convert_to_markdown.ignore_emphasis = True
    convert_to_markdown.skip_internal_links = True
    convert_to_markdown.ignore_images = True
    convert_to_markdown.ignore_mailto_links = True
    convert_to_markdown.ignore_links = True
    convert_to_markdown.include_sup_sub = True
    convert_to_markdown.body_width = 0

    # Stop the Markdown interpreter from escaping text it doesn't need to
    html2text.config.RE_MD_DASH_MATCHER = re.compile(r'(a^)(a^)')
    html2text.config.RE_MD_PLUS_MATCHER = re.compile(r'(a^)(a^)')
    html2text.config.RE_MD_DOT_MATCHER = re.compile(r'(a^)(a^)')
    html2text.config.RE_MD_BACKSLASH_MATCHER = re.compile(r'(a^)(a^)')

    # Convert the HTML
    markdown_description = convert_to_markdown.handle(str(html_content))

    edited_markdown: list[str] = []

    # Remove Markdown elements that won't work in Launchbox
    for line in markdown_description.split('\n'):
        # Blockquotes
        if line.startswith('> ') or line == '>':
            edited_markdown.append(re.sub('^> ?', '', line))
        # Headings
        elif re.search('#{1,6} ', line):
            edited_markdown.append(re.sub('^#{1,6} ', '', line))
        else:
            edited_markdown.append(line)

    markdown_description = '\n'.join(edited_markdown)

    # Remove extraneous new lines, and format the remaining new lines as something
    # Microsoft Access will understand
    markdown_description = re.sub('\n{3,}', '\n\n', markdown_description)
    markdown_description = markdown_description.replace('\n', '\r\n')
    markdown_description = markdown_description.strip()

    return markdown_description


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

    # Convert the HTML description to a restricted subset of Markdown
    if 'description' in df:
        df['description'] = df['description'].apply(description_to_markdown)

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
