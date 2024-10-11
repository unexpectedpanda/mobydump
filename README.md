# MobyDump

MobyDump is a command line application that downloads data from the MobyGames API for a
specific platform, and then outputs it to delimiter-separated value files for import into
Microsoft Access, or alternatively a JSON file. It's purpose-built for the
[Exo projects](https://github.com/exoscoriae).

Downloads are auto-resumed if the process is interrupted by the user and restarted, or if
select HTTP error codes are received.

## Before you begin

If you're not using the
[compiled release](https://github.com/unexpectedpanda/mobydump/releases), then you need to
set up your development environment. To do so, complete the following steps:

1.  [Install Python 3.10 or higher](https://www.python.org/).

1.  Open a terminal to install the required dependencies. You can do this with
    [Hatch](https://github.com/pypa/hatch) or pip.

    * **Hatch**. Run the following command to install Hatch:

      ```
      pip install hatch
      ```

      Navigate to where the `pyproject.toml` file is for MobyDump, and then enter the
      default environment:

      ```
      hatch shell
      ```

      Hatch installs the dependencies you need on the first run. You can now
      [run MobyDump](#run-mobydump) while inside this environment. When you're done with
      MobyDump, exit the environment:

      ```
      exit
      ```

    * **Pip**. Run the following command to install the dependencies with `pip`,
      potentially in combination with an environment manager of your choice:

      ```
      pip install -r requirements.txt
      ```

### Set up your API key and rate limit

No matter which variant of MobyDump you use, you need to set up your MobyGames API key. To
do so, complete the following steps:

1.  Create a file named `.env` in the same folder MobyDump is in.

1.  Add your MobyGames API key as follows, replacing `<MOBYGAMES_API_KEY>` with your
    API key:

    ```none
    MOBY_API="<MOBYGAMES_API_KEY>"
    ```

1.  You can also set the rate limit in this file, in seconds per request, instead of
    passing a command line argument:

    ```none
    MOBY_RATE=10
    ```

    Valid values are `10` for the legacy free API key (no longer issued by MobyGames), or
    `5` for the MobyPro API key.

    Use lower numbers at your own risk. Unless you have an agreement with MobyGames, lower
    numbers than are suitable for your API key could get your client or API key banned.

### Set up Dropbox for export (optional)

After MobyDump has saved output files to disk, you have the option to upload them to
Dropbox with `--dropbox`. The files are removed from the disk after upload.

To set up Dropbox uploading:

1.  Go to https://www.dropbox.com/developers/apps.

1.  Create a new app.

1.  Get your Dropbox app key and app secret, and assign them to
    `DROPBOX_APP_KEY` and `DROPBOX_APP_SECRET` in
    [the same `.env` file in which you set up your API key](#set-up-your-api-key-and-rate-limit):

    ```
    DROPBOX_APP_KEY="<YOUR_DROPBOX_APP_KEY>"
    DROPBOX_APP_SECRET="<YOUR_DROPBOX_APP_SECRET>"
    ```

1.  Visit the following URL, replacing `<DROPBOX_APP_KEY>` with your app key:

    ```
    https://www.dropbox.com/oauth2/authorize?client_id=<DROPBOX_APP_KEY>&response_type=code&token_access_type=offline
    ```

1.  Assign the access code you're given to `DROPBOX_ACCESS_CODE` in the `.env` file.

    ```
    DROPBOX_ACCESS_CODE="<YOUR_DROPBOX_ACCESS_CODE>"
    ```

1.  Run the `tools/get_dropbox_refresh_token.py` script. This uses your access code to get
    a refresh token. The refresh token allows you to request short-lived tokens on an
    ongoing basis. Short-lived tokens allow you to upload to your Dropbox.

    You can only use an access code once. If you get something wrong, you need to request
    another access code and run the script again.

1.  From the response to the script, assign the `refresh_key` value to
    `DROPBOX_REFRESH_TOKEN` in the `.env` file.

    ```
    DROPBOX_REFRESH_TOKEN="<YOUR_DROPBOX_REFRESH_TOKEN>"
    ```

Your `.env` file should now look something
like this, and you're ready to upload to Dropbox with `--dropbox`:

```
MOBY_API="aCompletelyFakeMobyAPIKey"
MOBY_RATE=10
DROPBOX_APP_KEY="aCompletelyFakeDropboxAppKey"
DROPBOX_APP_SECRET="aCompletelyFakeDropboxAppSecret"
DROPBOX_ACCESS_CODE="aCompletelyFakeDropboxAccessCode"
DROPBOX_REFRESH_TOKEN="aCompletelyFakeDropboxRefreshToken"
```

## Run MobyDump

How you run MobyDump changes depending on your platform. Open a terminal, change to the
folder MobyDump is in, and then run one of the following commands.

* Linux and MacOS:

    ```
    python3 mobydump.py
    ```

* Windows:

    ```
    mobydump.py
    ```

    or

    ```
    python mobydump.py
    ```

* Windows compiled:

    ```
    mobydump
    ```

### Basic usage

First get the platforms and their IDs.

```
mobydump.py -p
```

You receive a response that looks similar to the following example:

```
NAME                                          ID

1292 Advanced Programmable Video System             253
3DO                                                  35
ABC 80                                              318
APF MP1000/Imagination Machine                      213
Acorn - Electron                                     93
Acorn 32-bit                                        117
Adventure Vision                                    210
AirConsole                                          305
Alice 32/90                                         194
Altair 680                                          265
Altair 8800                                         222
Amazon Alexa                                        237
Amstrad - CPC                                        60
Amstrad PCW                                         136
Antstream                                           286
Apple - II                                           31
Apple - IIgs                                         51
Apple - Macintosh                                    74
Apple - iPad                                         96
Apple - iPhone                                       86
Apple - iPod Classic                                 80
Apple I                                             245
Arcade                                              143
...
```

Next, get the games based on a platform ID.

```
mobydump.py -g 35
```

See [command line flags](#command-line-flags) for all the options you can set when
downloading the games for a platform.

### Command line flags

The following flags are available to use.

```
options:
  -p, --platforms       Get the platforms and their IDs from MobyGames.

  -g <PLATFORM_ID>, --games <PLATFORM_ID>
                        Get all game details from MobyGames that belong to a specific
                        platform ID, and output the result to files. See flags that can be
                        used with --games to change this behavior.

  -u <NUMBER_OF_DAYS>, --update <NUMBER_OF_DAYS>
                        Update all the games details for the platforms you've already
                        downloaded, and output the result to files. See flags that can be
                        used with --update to change this behavior.

                        MobyGames only provides update data for the last 21 days. If
                        you've waited longer, you should redownload the platform from
                        scratch.
```

Flags that can be used with `--platforms`, `--games`, or `--update`:

```
  -c "<CACHE_PATH>", --cache "<CACHE_PATH>"
                        Change the cache path. Defaults to cache in the same folder
                        MobyDump is in.

  -ua "<USER_AGENT>", --useragent "<USER_AGENT>"
                        Change the user agent MobyDump supplies when making requests.
                        Defaults to:

                        MobyDump/0.8; https://github.com/unexpectedpanda/mobydump
```

Flags that can be used with `--games` or `--update`:

```
  -d "<DELIMITER>", --delimiter "<DELIMITER>"
                        The single character delimiter to use in the output files. Accepts
                        single-byte characters only. When not specified, defaults to tab.
                        Ignored if output is set to JSON.

  -db, --dropbox        ZIP the output files, upload them to Dropbox, and then delete the
                        local files.

  -fr, --forcerestart   Don't resume from where MobyDump last left off. Instead, restart
                        the request process from MobyGames. This deletes your cached files.

  -n, --noninteractive  Make MobyDump output less chatty for non-interactive terminals, so
                        logs don't get out of control.

  -o <FILE_TYPE_ID>, --output <FILE_TYPE_ID>
                        The file type to output to. When not specified, defaults to 1.
                        Choose a number from the following list:

                        0 - Don't output files
                        1 - Delimiter-separated value
                        2 - JSON
                        3 - Delimiter-separated value and JSON

                        Delimiter-separated value files are sanitized for problem
                        characters, JSON data is left raw.

  -pa "<FOLDER_PATH>", --path "<FOLDER_PATH>"
                        The folder to output files to. When not specified, defaults to
                        MobyDump's folder.

  -pr "<PREFIX>", --prefix "<PREFIX>"
                        The prefix to add to the beginning of output filenames. When not
                        specified, defaults to nothing. By default, the output files are
                        named as follows:

                        • Platform name - (Primary) Games.txt
                        • Platform name - Alternate titles.txt
                        • Platform name - Genres.txt
                        • Platform name - Attributes.txt
                        • Platform name - Releases.txt
                        • Platform name - Patches.txt
                        • Platform name - Product codes.txt
                        • Platform name - Ratings.txt

  -r <SECONDS_PER_REQUEST>, --ratelimit <SECONDS_PER_REQUEST>
                        How many seconds to wait between requests. When not specified,
                        defaults to 10. Overrides the MOBY_RATE environment variable.
                        Choose a number from the following list:

                        10 - MobyGames non-commercial free API key
                        5  - MobyPro non-commercial API key

                        Use lower numbers at your own risk. Unless you have an agreement
                        with MobyGames, lower numbers than are suitable for your API key
                        could get your client or API key banned.
```

## Known limitations

* There's nothing to stop you setting a lower seconds-per-request than is allowed for
  your API key, or running MobyDump multiple times in parallel. I strongly advise you to
  stick to the advertised limits and only run one session of MobyDump, or your client or
  API key could be banned by MobyGames for abuse.

## Import into Microsoft Access

Assuming you exported to delimiter-separated value files, here are the settings you need
to import them into Microsoft Access:

1.  Choose **Delimited** as the format, and then choose the delimiter (the default is
    tab).

1.  Change **Text Qualifier** to `"`.

1.  Enable **First row contains field names**.

1.  Microsoft Access doesn't detect all fields correctly. The following files contain
    fields whose field data type must be set manually before completing the import to
    avoid errors:

    <table>
      <thead>
        <tr>
          <th>File</th>
          <th>Field</th>
          <th>Field type</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td rowspan="2">Patches</td>
          <td><code>description</code></td>
          <td>Long text</td>
        </tr>
        <tr>
          <td><code>release_date</code></td>
          <td>Short text</td>
        </tr>
        <tr>
          <td>Product codes</td>
          <td><code>releases_release_date</code></td>
          <td>Short text</td>
        </tr>
        <tr>
          <td rowspan="2">Releases</td>
          <td><code>releases_description</code></td>
          <td>Long text</td>
        </tr>
        <tr>
          <td><code>releases_release_date</code></td>
          <td>Short text</td>
        </tr>
      </tbody>
    </table>

### Set up relationships

In the `Platform name - (Primary) Games` table, set `game_id` as the primary key, and then
use the relationships view to link the fields between the different tables you've created
by importing the delimiter-separated value files.

The column `releases_release_year` has been added to the Releases and Product codes files,
so you can build comparisons using the year as an integer. If you want, you can also link
this column between these tables.
