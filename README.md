# MobyDump

MobyDump downloads data from the MobyGames API for a specific platform, and outputs it to
a delimiter-separated value file or JSON. It's purpose-built for the [Exo projects](https://github.com/exoscoriae).

MobyDump auto-resumes the download if the process is interrupted by the user, or if select
HTTP error codes are received.

## Before you begin

If you're not using the [compiled release](https://github.com/unexpectedpanda/mobydump/releases),
then you need to set up your development environment. To do so, complete the following
steps:

1.  [Install Python 3.10 or higher](https://www.python.org/).

1.  Install the required dependencies.

    ```
    pip install numpy pandas requests
    ```

### Set up your API key

No matter which version of MobyDump you use, you need to set up your MobyGames API key. To
do so, complete the following steps:

1.  Create a file named `.env` in the same folder MobyDump is in.

1.  Add your MobyGames API key as follows, replacing `<MOBYGAMES_API_KEY>` with your
    API key:

    ```none
    MOBY_API="<MOBYGAMES_API_KEY>"
    ```

## Using MobyDump

Assuming Python is set up correctly, you can run MobyDump as follows:

```
python3 mobydump.py
```

On Windows, you can possibly run MobyDump directly:

```
mobydump.py
```

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
                        The single character delimiter to use in the output file.
                        Accepts single-byte characters only. When not specified,
                        defaults to tab. Ignored if type is set to JSON.

  -f <FILE_TYPE_ID>, --filetype <FILE_TYPE_ID>
                        The file type to output to. When not specified, defaults to 1.
                        Choose a number from the following list:

                        1 - Delimiter separated value
                        2 - JSON

  -o "<FILENAME>", --output "<FILENAME>"
                        The filename to output to. When not specified, defaults to
                        output.txt.

  -r <SECONDS_PER_REQUEST>, --ratelimit <SECONDS_PER_REQUEST>
                        How many seconds to wait between requests. When not specified,
                        defaults to 10. Choose a number from the following list:

                        10 - MobyGames non-commercial free API key
                        5  - MobyPro non-commercial API key

                        Use lower numbers at your own risk. Unless you have an
                        agreement with MobyGames, lower numbers than are suitable for
                        your API key could get your client or API key banned.

  --raw                 Don't format the output text or re-arrange columns. This is
                        a compatibility setting for if MobyGames changes its API responses.
                        Ignored if type is set to JSON.

  -u "<USER_AGENT>", --useragent "<USER_AGENT>"
                        Change the user agent MobyDump supplies when making requests.
                        Defaults to MobyDump/0.1; https://www.retro-exo.com/.
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

## Importing into Access 2013&ndash;2021

1.  Open the file that MobyDump created.

1.  Choose **Delimited** as the format.

1.  Click **Next**.

1.  Choose the delimiter.

1.  Click **First row contains field names**.

1.  Change **Text Qualifier** to `"`.

1.  Click **Finish**.
