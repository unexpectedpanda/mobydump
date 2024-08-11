import argparse
import sys
import textwrap

from typing import Any

def eprint(
    text: str = '', wrap=True, level='', indent: int = 2, pause=False, overwrite=False, **kwargs
) -> None:
    """
    Prints to STDERR.

    Args:
        text (str, optional): The content to tprint. Defaults to `''`.
        wrap (bool, optional): Whether to wrap text. Defaults to `True`.
        level (str, optional): How the text is formatted. Valid values include `warning`,
          `error`, `success`, `disabled`, `heading`, `subheading`. Defaults to `''`.
        indent (int, optional): After the first line, how many spaces to indent whenever
          a text wraps to a new line. Defaults to `2`.
        pause (bool, optional): Shows a `Press enter to continue` message and waits for
          use input. Defaults to `False`.
        overwrite (bool, optional): Delete the previous line and replace it with this one.
          Defaults to `False`.
        **kwargs: Any other keyword arguments to pass to the `print` function.
    """
    indent_str: str = ''
    new_line: str = ''
    overwrite_str: str = ''

    if text:
        indent_str = ' '

    if overwrite:
        overwrite_str = '\033M\033[2K'

    if level == 'warning':
        color = Font.warning
    elif level == 'error':
        color = Font.error
        new_line = '\n'
    elif level == 'success':
        color = Font.success
    elif level == 'disabled':
        color = Font.disabled
    elif level == 'heading':
        color = Font.heading_bold
    elif level == 'subheading':
        color = Font.subheading
    else:
        color = Font.end

    message: str = f"{overwrite_str}{color}{text}{Font.end}"

    if wrap:
        if level == 'heading':
            print(f'\n\n{Font.heading_bold}{"─"*95}{Font.end}', file=sys.stderr)  # noqa: T201
        if level == 'subheading':
            print(f'\n{Font.subheading}{"─"*60}{Font.end}', file=sys.stderr)  # noqa: T201
        print(  # noqa: T201
            f'{new_line}{textwrap.TextWrapper(width=95, subsequent_indent=indent_str*indent, replace_whitespace=False, break_long_words=False, break_on_hyphens=False).fill(message)}',
            file=sys.stderr,
            **kwargs,
        )
        if level == 'heading':
            print('\n')  # noqa: T201
    else:
        print(message, file=sys.stderr, **kwargs)  # noqa: T201

    if pause:
        empty_lines: str = '\n'

        if not text:
            empty_lines: str = ''

        print(  # noqa: T201
            f'{empty_lines}{Font.d}Press enter to continue{Font.end}', file=sys.stderr
        )
        input()

class Font:
    """Console text formatting."""

    success: str = '\033[0m\033[92m'
    success_bold: str = '\033[1m\033[92m'
    warning: str = '\033[0m\033[93m'
    warning_bold: str = '\033[1m\033[93m'
    error: str = '\033[0m\033[91m'
    error_bold: str = '\033[1m\033[91m'
    heading: str = '\033[0m\033[36m'
    heading_bold: str = '\033[1m\033[36m'
    subheading: str = '\033[0m\033[35m'
    subheading_bold: str = '\033[1m\033[35m'
    disabled: str = '\033[90m'
    bold: str = '\033[1m'
    bold_end: str = '\033[22m'
    italic = '\033[3m'
    italic_end = '\033[23m'
    underline: str = '\033[4m'
    underline_end = '\033[24m'
    plain = '\033[22m\033[23m\033[24m'
    end: str = '\033[0m'

    b: str = bold
    be: str = bold_end
    d: str = disabled
    i: str = italic
    ie: str = italic_end
    u: str = underline
    ue: str = underline_end
    overwrite: str = '\033M\033[2K'


class SmartFormatter(argparse.HelpFormatter):
    """
    Text formatter for argparse that respects new lines.

    From https://stackoverflow.com/questions/3853722/how-to-insert-newlines-on-argparse-help-text
    """

    def _split_lines(self, text: str, width: int) -> list[Any]:
        if text.startswith('R|'):
            return text[2:].splitlines()
        return argparse.HelpFormatter._split_lines(self, text, width)