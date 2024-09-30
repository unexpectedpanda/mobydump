import sys
from time import gmtime, sleep, strftime

import requests

from modules.utils import Config, eprint


def api_request(
    url: str, config: Config, message: str = '', timeout: int = 0
) -> requests.models.Response:
    """
    Requests data from the MobyGames API.

    Args:
        url (str): The URL to query, including query strings.

        config (Config): The MobyDump config object instance.

        message (str): The message to print to screen.

        timeout (int): How long to wait to make the request, in seconds. Only used
            if the request needs to be retried.

    Returns:
        requests.models.Response: The response from the MobyGames API.
    """
    try:
        eprint(message, wrap=False)

        response = requests.get(url, headers=config.headers)

        response.raise_for_status()
    except requests.exceptions.Timeout:
        response = request_retry(url, config, message, timeout, 'Timeout.')
    except requests.ConnectionError:
        response = request_retry(
            url,
            config,
            message,
            timeout,
            'Can\'t connect to the MobyGames API, maybe the internet has dropped?',
        )
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 401:
            eprint(
                'Unauthorized access (401). Have you provided a MobyGames API key?',
                level='error',
                indent=0,
            )
            eprint(f'\n{err}')
            sys.exit(1)
        elif err.response.status_code == 422:
            eprint(
                'Unprocessable content (422). The parameter sent was the right type, but was invalid.',
                level='error',
                indent=0,
            )
            eprint(f'\n{err}')
            sys.exit(1)
        elif err.response.status_code == 429 or 'Too Many Requests for url' in str(err):
            response = request_retry(
                url,
                config,
                message,
                timeout,
                'Rate limited (429). Too many requests in too short a time.',
            )
        elif err.response.status_code == 500:
            # Sometimes MobyGames throws a 500, even though it shouldn't. Attempt a retry
            # if this happens.
            response = request_retry(
                url,
                config,
                message,
                timeout,
                'Internal server error (500). Assuming the issue\'s ephemeral.',
            )
        elif err.response.status_code == 502:
            # Sometimes MobyGames throws a 502. Attempt a retry if this happens.
            response = request_retry(
                url,
                config,
                message,
                timeout,
                'Bad gateway error (502). Assuming the issue\'s ephemeral.',
            )
        elif err.response.status_code == 503:
            response = request_retry(
                url,
                config,
                message,
                timeout,
                'Service unavailable (503). Assuming the issue\'s ephemeral.',
            )
        elif err.response.status_code == 504:
            response = request_retry(
                url,
                config,
                message,
                timeout,
                'Gateway timeout for URL (504). Assuming the issue\'s ephemeral.',
            )
        elif err.response.status_code == 520:
            response = request_retry(
                url,
                config,
                message,
                timeout,
                'Cloudflare: Web server returned an unknown error (520). Assuming the issue\'s ephemeral.',
            )
        elif err.response.status_code == 522 or err.response.status_code == 524:
            response = request_retry(
                url,
                config,
                message,
                timeout,
                f'Cloudflare: Origin server timed out ({err.response.status_code}). Assuming the issue\'s ephemeral.',
            )
        else:
            eprint(f'\n{err}', level='error', indent=0)
            sys.exit(1)

    return response


def request_retry(
    url: str, config: Config, message: str, timeout: int, error_message: str
) -> requests.models.Response:
    """
    Retries a request if a timeout has occurred.

    Args:
        url (str): The URL to query, including query strings.

        config (Config): The MobyDump config object instance.

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

    non_interactive_output: bool = False

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
                if not non_interactive_output:
                    eprint(
                        f'• {error_message} Retry #{timeout} in {strftime("%H:%M:%S", gmtime(progressive_timeout[timeout] - j))}...',
                        level='warning',
                        overwrite=True,
                        wrap=False,
                    )
                if config.args.noninteractive:
                    non_interactive_output = True
                sleep(1)

        timeout += 1

        response = api_request(url, config, message, timeout)

    return response


def request_wait(config: Config) -> None:
    """
    A countdown timer that limits the rate of requests.

    Args:
        rate_limit (int): How many seconds to wait between requests.
    """
    non_interactive_output: bool = False

    for i in range(config.rate_limit):
        if not non_interactive_output:
            eprint(f'• Waiting {config.rate_limit-i} seconds until next request...', overwrite=True)

        if config.args.noninteractive:
            non_interactive_output = True
        sleep(1)

    # Delete the previous line printed to screen
    eprint('\033M\033[2K\033M')
