import sys
from time import gmtime, sleep, strftime

import requests

from modules.utils import eprint


def api_request(
    url: str, headers: dict[str:str], message: str = '', timeout: int = 0
) -> requests.models.Response:
    """
    Requests data from the MobyGames API.

    Args:
        url (str): The URL to query, including query strings.

        headers (str): The headers for the request.

        message (str): The message to print to screen.

        timeout (int): How long to wait to make the request, in seconds. Only used
            if the request needs to be retried.

    Returns:
        requests.models.Response: The response from the MobyGames API.
    """
    try:
        eprint(message, wrap=False)

        response = requests.get(url, headers=headers)

        response.raise_for_status()
    except requests.exceptions.Timeout:
        response = request_retry(url, headers, message, timeout, 'Timeout.')
    except requests.ConnectionError:
        response = request_retry(
            url,
            headers,
            message,
            timeout,
            'Can\'t connect to the MobyGames API, maybe the internet has dropped?',
        )
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 401:
            eprint(
                'Unauthorized access. Have you provided a MobyGames API key?',
                level='error',
                indent=0,
            )
            eprint(f'\n{err}')
            sys.exit(1)
        if err.response.status_code == 422:
            eprint(
                'The parameter sent was the right type, but was invalid.',
                level='error',
                indent=0,
            )
            eprint(f'\n{err}')
            sys.exit(1)
        if err.response.status_code == 429:
            response = request_retry(
                url,
                headers,
                message,
                timeout,
                'Rate limited: too many requests in too short a time.',
            )
        if err.response.status_code == 500:
            # Sometimes MobyGames throws a 500, even though it shouldn't. Attempt a retry
            # if this happens.
            response = request_retry(
                url,
                headers,
                message,
                timeout,
                'Received a 500 internal server error, assuming it\'s ephemeral.',
            )
        if err.response.status_code == 502:
            # Sometimes MobyGames throws a 502. Attempt a retry if this happens.
            response = request_retry(
                url,
                headers,
                message,
                timeout,
                'Received a 502: bad gateway error, assuming it\'s ephemeral.',
            )
        if err.response.status_code == 504:
            response = request_retry(url, headers, message, timeout, 'Gateway timeout for URL.')
        elif 'Too Many Requests for url' in str(err):

            response = request_retry(url, headers, message, timeout, 'Too many requests for URL.')
        else:
            eprint(f'\n{err}', level='error', indent=0)
            sys.exit(1)

    return response


def request_retry(
    url: str, headers: dict[str, str], message: str, timeout: int, error_message: str
) -> requests.models.Response:
    """
    Retries a request if a timeout has occurred.

    Args:
        url (str): The URL to query, including query strings.

        headers (str): The headers for the request.

        message (str): The message to print to screen.

        timeout (int): How long to wait to make the request, in seconds. Only used
            if the request needs to be retried.

        error_message (str): The error message to print to screen.

    Returns:
        requests.models.Response: The response from the MobyGames API.
    """
    # Progressively increase the timeout with each retry
    progressive_timeout: list[int] = [0, 60, 300, 600, 3600, -1]

    # Set an empty response with a mock error code
    response: requests.models.Response = requests.models.Response()
    response.status_code = 418

    while response.status_code != 200:
        if progressive_timeout[timeout] == -1:
            eprint(
                f'\n{error_message} Too many retries, exiting...',
                level='error',
                overwrite=True,
                indent=0,
            )
            sys.exit(1)
        else:
            for j in range(progressive_timeout[timeout]):
                eprint(
                    f'• {error_message} Retry #{timeout} in {strftime("%H:%M:%S", gmtime(progressive_timeout[timeout] - j))}...',
                    level='warning',
                    overwrite=True,
                    wrap=False,
                )
                sleep(1)

        timeout += 1

        response = api_request(url, headers, message, timeout)

    return response


def request_wait(rate_limit: int) -> None:
    """
    A countdown timer that limits the rate of requests.

    Args:
        rate_limit (int): How many seconds to wait between requests.
    """
    for i in range(rate_limit):
        eprint(f'• Waiting {rate_limit-i} seconds until next request...', overwrite=True)
        sleep(1)

    # Delete the previous line printed to screen
    eprint('\033M\033[2K\033M')
