# MobyDump

MobyDump is a command line application that downloads data from the MobyGames API for a
specific platform, and then outputs it to delimiter-separated value files for import into
Microsoft Access, or alternatively a JSON file. It's purpose-built for the
[Exo projects](https://github.com/exoscoriae).

MobyDump auto-resumes the download if the process is interrupted by the user, or if select
HTTP error codes are received.

## Before you begin

If you're not using the
[compiled release](https://github.com/unexpectedpanda/mobydump/releases), then you need to
set up your development environment. To do so, complete the following steps:

1.  [Install Python 3.10 or higher](https://www.python.org/).

1.  Install the required dependencies.

    ```
    pip install numpy pandas requests
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

    Valid values are `10` for the free API key, or `5` for the MobyPro API key.

    Use lower numbers at your own risk. Unless you have an agreement with MobyGames, lower
    numbers than are suitable for your API key could get your client or API key banned.

## Using MobyDump

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

1292 Advanced Programmable Video System      253
3DO                                           35
ABC 80                                       318
APF MP1000/Imagination Machine               213
Acorn 32-bit                                 117
Adventure Vision                             210
AirConsole                                   305
Alice 32/90                                  194
Altair 680                                   265
Altair 8800                                  222
Amazon Alexa                                 237
Amiga                                         19
Amiga CD32                                    56
Amstrad CPC                                   60
Amstrad PCW                                  136
Android                                       91
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
                        Get all game details from MobyGames that belong
                        to a specific platform ID.
```

Flags that can be used with `--games`:

```
  -d "<DELIMITER>", --delimiter "<DELIMITER>"
                        The single character delimiter to use in the output files.
                        Accepts single-byte characters only. When not specified,
                        defaults to tab. Ignored if filetype is set to JSON.

  -f <FILE_TYPE_ID>, --filetype <FILE_TYPE_ID>
                        The file type to output to. When not specified, defaults to 1.
                        Choose a number from the following list:

                        1 - Delimiter separated value
                        2 - JSON

                        Delimiter separated value files are sanitized for problem characters,
                        JSON data is left raw.

  -pr "<PREFIX>", --prefix "<PREFIX>"
                        The prefix to add to the output files. Ignored if filetype
                        is set to JSON. When not specified, defaults to nothing.
                        By default, the output files are named as follows:

                        • 1) Platform name - Games.txt
                        • 2) Platform name - Alternate titles.txt
                        • 3) Platform name - Genres.txt
                        • 4) Platform name - Attributes.txt
                        • 5) Platform name - Releases.txt
                        • 6) Platform name - Patches.txt
                        • 7) Platform name - Product codes.txt
                        • 8) Platform name - Ratings.txt

                        If a prefix is specified, it's inserted between the number and the
                        platform name.

  -r <SECONDS_PER_REQUEST>, --ratelimit <SECONDS_PER_REQUEST>
                        How many seconds to wait between requests. When not specified,
                        defaults to 10. Choose a number from the following list:

                        10 - MobyGames non-commercial free API key
                        5  - MobyPro non-commercial API key

                        Use lower numbers at your own risk. Unless you have an
                        agreement with MobyGames, lower numbers than are suitable for
                        your API key could get your client or API key banned.

  -u "<USER_AGENT>", --useragent "<USER_AGENT>"
                        Change the user agent MobyDump supplies when making requests.
                        Defaults to MobyDump/0.3; https://www.retro-exo.com/.
```

## Known limitations

* If the internet drops, you need to manually restart MobyDump. At this stage it's unclear
  why, but an auto-retry crashes MobyDump in this situation.

* Memory usage can get as high as ~900MB when processing the Windows platform dataset.
  Given MobyDump's limited use-case and audience, and the abundance of RAM on modern PCs,
  it's not worth optimizing this at this stage.

* There's nothing to stop you setting a lower seconds-per-request than is allowed for
  your API key, or running MobyDump multiple times in parallel. I strongly advise you to
  stick to the advertised limits and only run one session of MobyDump, or your client or
  API key could be banned by MobyGames for abuse.

## Importing into Microsoft Access

Assuming you exported to delimiter-separated value files, here are the settings you need
to import them into Microsoft Access:

1.  Choose **Delimited** as the format, and then choose the delimiter.

1.  Change **Text Qualifier** to `"`.

1.  Select **First row contains field names**.

1.  The following files contain fields whose field data type must be set manually before
    completing the import to avoid errors:

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
          <td>Patches</td>
          <td><code>description</code></td>
          <td>Long text</td>
        </tr>
        <tr>
          <td>Product codes</td>
          <td><code>releases_release_date</code></td>
          <td>Short text</td>
        </tr>
        <tr>
          <td rowspan="2">Releases</td>
          <td><code>releases_release_date</code></td>
          <td>Short text</td>
        </tr>
        <tr>
          <td><code>releases_description</code></td>
          <td>Long text</td>
        </tr>
      </tbody>
    </table>
