import pathlib
import sys
from time import gmtime, sleep, strftime

import requests

from modules.utils import Config, eprint


def api_request(
    url: str, config: Config, message: str = '', timeout: int = 0, type: str = ''
) -> requests.models.Response:
    """
    Requests data from the MobyGames API.

    Args:
        url (str): The URL to query, including query strings.

        config (Config): The MobyDump config object instance.

        message (str): The message to print to screen.

        timeout (int): How long to wait to make the request, in seconds. Only used
            if the request needs to be retried.

        type (str): What type of API request is being made. Valid options are
            '' or 'game-details'.

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
        elif err.response.status_code == 404 and type == 'game-details':
            eprint(
                '• URL not found (404). The game has likely been assigned to another ID, and the platform needs updating. Skipping...',
                level='warning',
                wrap=False,
            )
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
        elif err.response.status_code == 525:
            response = request_retry(
                url,
                config,
                message,
                timeout,
                f'Cloudflare: SSL handshake failed ({err.response.status_code}). Assuming the issue\'s ephemeral.',
            )
        elif str(err.response.status_code).startswith('5'):
            response = request_retry(
                url,
                config,
                message,
                timeout,
                f'Server error ({err.response.status_code}). Assuming the issue\'s ephemeral.',
            )
        else:
            eprint(f'\n{err}', level='error', indent=0)
            sys.exit(1)

    return response


def download_file(url: str, local_filename: pathlib.Path) -> None:
    """
    Downloads a file in chunks.

    Code from: https://stackoverflow.com/questions/16694907/download-large-file-in-python-with-requests

    Args:
        url (str): The URL to download from.
        local_filename (pathlib.Path): The local file to save to.

    Returns:
        str: The filename
    """
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                # If you have a chunk encoded response, uncomment the 'if'
                # and set chunk_size parameter to None.
                # if chunk:
                f.write(chunk)


def get_dropbox_short_lived_token(config: Config) -> requests.Response:
    """
    Gets a short-lived token from Dropbox for uploading files.

    Args:
        config (Config): The MobyDump config object instance.

    Returns:
        requests.Response: The response to the token request.
    """
    data = {
        'refresh_token': config.dropbox_refresh_token,
        'grant_type': 'refresh_token',
        'client_id': config.dropbox_app_key,
        'client_secret': config.dropbox_app_secret,
    }

    try:
        response = requests.post('https://api.dropbox.com/oauth2/token', data=data)

        response.raise_for_status()
    except Exception:
        # Try to get the token one more time, then exit on fail
        request_wait(config, wait_override=5)

        response = get_dropbox_short_lived_token(config)

        response.raise_for_status()

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


def request_wait(config: Config, wait_override: int = 0) -> None:
    """
    A countdown timer that limits the rate of requests.

    Args:
        config (Config): The MobyDump config object instance.
        wait_override (int): The number of seconds to use for the wait period, overriding
          the value stored in the config object.
    """
    non_interactive_output: bool = False

    countdown: int|float = config.rate_limit

    if wait_override:
        countdown = wait_override

    if countdown < 1:
        if not non_interactive_output:
                eprint(f'• Waiting {countdown} seconds until next request...', overwrite=True)
        sleep(countdown)
    else:
        for i in range(int(countdown)):
            if not non_interactive_output:
                if int(countdown) - i == 1:
                    eprint(f'• Waiting {int(countdown) - i} second until next request...', overwrite=True)
                else:
                    eprint(f'• Waiting {int(countdown) - i} seconds until next request...', overwrite=True)

            if config.args.noninteractive:
                non_interactive_output = True
            sleep(1)

    # Delete the previous line printed to screen
    eprint('\033M\033[2K\033M')
