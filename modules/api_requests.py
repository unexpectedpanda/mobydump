import requests
import sys

from modules.utils import eprint


def mobygames_request(url: str) -> requests.models.Response:
    headers: dict[str, str] = {'Accept': 'application/json'}

    try:
        response = requests.get(url, headers=headers)

        return response
    except requests.exceptions.Timeout:
        eprint('Timeout, trying again in x seconds')
        sys.exit(1)
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 401:
            eprint('Unauthorized access. Have you provided a MobyGames API key?')
            eprint(f'\n{err}')
            sys.exit(1)
        if err.response.status_code == 422:
            eprint('The parameter sent was the right type, but was invalid.')
            eprint(f'\n{err}')
            sys.exit(1)
        if err.response.status_code == 429:
            eprint('Too many requests, trying again in x seconds...')
            eprint(f'\n{err}')
            sys.exit(1)
        if err.response.status_code == 504:
            eprint('Gateway timeout for URL, trying again in x seconds...')
            eprint(f'\n{err}')
            sys.exit(1)
        else:
            eprint(f'\n{err}')
            sys.exit(1)