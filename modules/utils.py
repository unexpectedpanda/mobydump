import argparse
import os
import pathlib
import platform
import re
import requests
import sys
import textwrap
from typing import Any


class Config:
    def __init__(
        self,
        args: argparse.Namespace,
        api_key: str,
        dropbox_refresh_token: str,
        dropbox_app_key: str,
        dropbox_app_secret: str,
        rate_limit: int,
        headers: dict[str, str],
        output_file_type: int,
        output_path: str,
        prefix: str,
        delimiter: str,
        cache: pathlib.Path,
        dropbox_access_token: str = ''
    ) -> None:
        """
        Creates an object that contains internal config data.

        Args:
            args (argparse.Namespace): The arguments passed in by the user.
            api_key (str): The MobyGames API key.
            dropbox_refresh_token (str): The refresh token for your Dropbox app.
            dropbox_app_key (str): The app key for your Dropbox app.
            dropbox_app_secret (str): The app secret for your Dropbox app.
            rate_limit (int): The rate limit in seconds per request.
            headers (dict[str, str]): The headers to use in the API request.
            output_file_type (int): The type of file to output to. Options are:
                0 - Don't output files
                1 - Delimiter separated value
                2 - JSON
            output_path (str): The folder to write output files to.
            prefix (str): The prefix to add to the beginning of output filenames.
            delimiter (str): The single character delimiter to use in the output files.
            cache (str): The path to the cache folder
            dropbox_access_token (str): The short lived access token that's used to upload
              files to Dropbox.
        """
        self.args = args
        self.api_key = api_key
        self.dropbox_refresh_token = dropbox_refresh_token
        self.dropbox_app_key = dropbox_app_key
        self.dropbox_app_secret = dropbox_app_secret
        self.dropbox_access_token = dropbox_access_token
        self.rate_limit = rate_limit
        self.headers = headers
        self.output_file_type = output_file_type
        self.output_path = output_path
        self.prefix = prefix
        self.delimiter = delimiter
        self.cache = cache


def enable_vt_mode() -> Any:
    """
    Turns on VT-100 emulation mode for Windows, allowing things like colors.

    From https://bugs.python.org/issue30075
    """
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32: ctypes.WinDLL = ctypes.WinDLL('kernel32', use_last_error=True)

    ERROR_INVALID_PARAMETER: int = 0x0057
    ENABLE_VIRTUAL_TERMINAL_PROCESSING: int = 0x0004

    def _check_bool(result: int, func: Any, args: tuple[int, Any]) -> tuple[int, Any]:
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        return args

    LPDWORD = ctypes.POINTER(wintypes.DWORD)
    setattr(kernel32.GetConsoleMode, 'errcheck', _check_bool)
    setattr(kernel32.GetConsoleMode, 'argtypes', (wintypes.HANDLE, LPDWORD))
    setattr(kernel32.GetConsoleMode, 'errcheck', _check_bool)
    setattr(kernel32.SetConsoleMode, 'argtypes', (wintypes.HANDLE, wintypes.DWORD))

    def set_conout_mode(new_mode: int, mask: int = 0xFFFFFFFF) -> int:
        # Don't assume STDOUT is a console, open CONOUT$ instead
        fdout: int = os.open('CONOUT$', os.O_RDWR)
        try:
            hout: int = msvcrt.get_osfhandle(fdout)
            old_mode: ctypes.c_ulong = wintypes.DWORD()
            kernel32.GetConsoleMode(hout, ctypes.byref(old_mode))
            mode: int = (new_mode & mask) | (old_mode.value & ~mask)
            kernel32.SetConsoleMode(hout, mode)
            return old_mode.value
        finally:
            os.close(fdout)

    mode = mask = ENABLE_VIRTUAL_TERMINAL_PROCESSING

    try:
        return set_conout_mode(mode, mask)
    except OSError as e:
        if e.winerror == ERROR_INVALID_PARAMETER:
            raise NotImplementedError
        raise


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


def get_dropbox_short_lived_token(config):
    data = {
                'refresh_token': config.dropbox_refresh_token,
                'grant_type': 'refresh_token',
                'client_id': config.dropbox_app_key,
                'client_secret': config.dropbox_app_secret,
            }

    response = requests.post('https://api.dropbox.com/oauth2/token', data=data)

    return response


def old_windows() -> bool:
    """Figures out if MobyDump is running on a version of Windows earlier than Windows 10 or Windows Server 2019."""
    windows_version: str = platform.release()

    if sys.platform.startswith('win'):
        # Catch Windows Server
        if re.search('[A-Za-z]', windows_version):
            if int(re.sub('[A-Za-z]', '', windows_version)) < 2019:
                return True
        # Catch consumer versions of Windows
        elif float(windows_version) < 10:
            return True
    return False


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
