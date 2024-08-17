import sys
from time import sleep

import requests

from modules.utils import eprint


def mobygames_request(url: str, message: str = '', timeout: int = 0) -> requests.models.Response:
    """
    Requests data from the MobyGames API.

    Args:
        url (str): The URL to query, including query strings.

        message (str): The message to print to screen.

        timeout (int): How long to wait to make the request, in seconds. Only used
            if the request needs to be retried.

    Returns:
        requests.models.Response: The response from the MobyGames API.
    """
    try:
        eprint(message)

        response = requests.get(url, headers={'Accept': 'application/json'})

        response.raise_for_status()

        return response
    except requests.exceptions.Timeout:
        request_retry(url, message, timeout, 'Timeout.')
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 401:
            eprint('Unauthorized access. Have you provided a MobyGames API key?', level='error')
            eprint(f'\n{err}')
            sys.exit(1)
        if err.response.status_code == 422:
            eprint('The parameter sent was the right type, but was invalid.', level='error')
            eprint(f'\n{err}')
            sys.exit(1)
        if err.response.status_code == 429:
            request_retry(
                url, message, timeout, 'Rate limited: too many requests in too short a time.'
            )
        if err.response.status_code == 504:
            request_retry(url, message, timeout, 'Gateway timeout for URL.')
        else:
            eprint(f'\n{err}')
            sys.exit(1)


def request_retry(
    url: str, message: str, timeout: int, error_message: str
) -> requests.models.Response:
    """
    Retries a request if a timeout has occurred.

    Args:
        url (str): The URL to query, including query strings.

        message (str): The message to print to screen.

        timeout (int): How long to wait to make the request, in seconds. Only used
            if the request needs to be retried.

        error_message (str): The error message to print to screen.

    Returns:
        requests.models.Response: The response from the MobyGames API.
    """
    progressive_timeout: list[int] = [0, 60, 120, 300, 600, -1]

    if progressive_timeout[timeout] == -1:
        eprint(
            f'\n{error_message} Too many retries, exiting...',
            level='error',
            overwrite=True,
            indent=False,
        )
        sys.exit(1)
    else:
        for j in range(progressive_timeout[timeout]):
            eprint(
                f'• {error_message} Retry #{timeout} in {progressive_timeout[timeout] - j} seconds...',
                level='warning',
                overwrite=True,
                wrap=False,
            )
            sleep(1)

    timeout += 1
    response = mobygames_request(url, message, timeout)
    return response
