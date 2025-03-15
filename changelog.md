# Changelog

# v0.9.4 (15 February 2025)

- Added new MobyGames API plan details.

- Set the default rate to 1 request every 5 seconds, down from 1 request every 10 seconds.

# v0.9.3 (20 November 2024)

- Enabled `--writefromcache` for `--games`.

# v0.9.2 (17 November 2024)

- Added a flag, `--updatecache`. Must be used with `--update`. This only downloads the
  games MobyGames has updated in the given time period, and stores them in cache.
  Individual game details for each platform aren't updated, and no files are written.
  Useful for separating these update stages in things like GitHub Actions. Likely used as
  a step before `--writefromcache`.

- Added a flag, `--writefromcache`. Must be used with `--update`. As long as an update
  cache already exists on the disk, downloads individual game detail updates for each
  platform, and writes output files. Likely used as a step after `--updatecache`. If the
  update cache doesn't exist, it first downloads the games MobyGames has updated in the
  given time period.

# v0.9.1 (12 November 2024)

- MobyDump now only warns, and longer skips an update for a system that hasn't been
  updated locally for more than 21 days. This is because MobyGames might not update a
  system's titles for more than 21 days, as opposed to a user not running an update often
  enough.

- You can now specify a range of platforms to update with `--updaterange`. For example,
  instead of updating all platforms found on the local disk, `--updaterange 1 4` updates
  only platforms 1&ndash;4. To download a single platform, specify the same number twice:
  `--updaterange 1 1`. This can help to limit updates to specific platforms when
  trying to take things into account like GitHub Action runtime limits.

- A time estimate is now given for platform updates.

# v0.9.0 (10 October 2024)

- Fixed MobyDump crashing if a MobyGames platform has no games.

- Instead of exiting when MobyDump hits a 404 on downloading game details, it now
  progresses to the next game in the list. You might get a 404, for example, when
  someone accidentally creates a new game ID for a game that already exists in MobyGames'
  database, and it gets removed before MobyDump has a chance to download its details.

- The description field in delimiter-separated value files is now converted from HTML to
  a restricted subset of Markdown. This makes it easier to search and work with in fields
  that only support plain text.

- During updates, platforms with no updates no longer have their cache files rewritten.

- Fixed an estimated completion time bug.

- Fixed MobyDump being too eager to make a new request if a platform had less than 100
  titles, which caused a 429 error.

- Fixed duplicates possibly being written out to delimiter-separated value and JSON files.
  This can happen due to timing issues when initially requesting games from MobyGames
  during stage 1, resulting in duplicates entering the cache. While it's preferable to
  stop duplicates entering the cache in the first place, it's easier to filter them out
  during the export stage, so that is what has been done.

# v0.8 (29 September 2024)

- Breaking change: the `compress-json-python` library is now used to minify the cache and
  make it even smaller, at the cost of compute time. Caches written by v0.8 and higher
  aren't compatible with earlier versions of MobyDump.

- You can now upload output files to Dropbox instead of keeping them locally.

- The cache file location can now be specified by the user.

- Added a non-interactive mode to cut down on screen output for logging.

- Dropped the `sample_screenshots` key from the cache. This is because MobyGames
  returns random contents in the array, which causes needless diffs that take up space
  when a game is updated.

- You can now output to both JSON and delimiter-separated value files instead of just one
  when processing finishes.

- A time estimate is now given for completion of stage two.

- MobyGames' very basic platform names now have manufacturers added.

- Fixed JSON output.

# v0.7 (25 September 2024)

- MobyDump now outputs cache files with removed whitespace, which saves several hundred MB
  of disk space for the entire set of platform data.

# v0.6 (22 September 2024)

- Fixed a crash when a platform name uses invalid characters for a filepath.

- Slight rework of HTTP error handling.

- Added a basic catch for corrupt game details files.

- Improved some messages written to screen.

## v0.5 (19 September 2024)

- Fixed the retry function, and now things properly resume when the internet drops.

## v0.4 (18 September 2024)

- Some small crash fixes.

## v0.3 (15 September 2024)

- Extra game details are now pulled from the `/games/{game_id}/platforms/{platform_id}`
  endpoint after the initial details have been pulled from
  `/games?platform={platform_id}`. This is necessarily slow, as you can only request one
  game at a time, unlike `/games?platform={platform_id}` which returns 100 games at a
  time. This, in combination with a 5 second MobyPro rate limit means completing the DOS
  set, which has 8,461 titles at the time of writing, will take just under 12 hours.
  The Windows platform, at 90,500 titles, will take around 126 hours.
  Double those times if you're using the free API key.

  It'd be significantly more time efficient if MobyGames included the single game endpoint
  data in the `/games?platform={platform_id}` response, but sadly it isn't so.

- You can now update the game details of already downloaded platforms. MobyGames only
  returns a maximum of the last 21 days of updates, so if you've waited longer than that,
  you should download the platform again.

- You can now set the rate limit in the `.env` file, so you don't need to add the command
  line argument each time.

- You can now set the folder to output files to with the `--path` flag.

- Major restructuring has been done so multiple files are exported for different sets of
  data. This is to work with the different data shapes, as well as the Microsoft Access
  limit of 255 columns, and line length limit of 65,534 characters.

- Because Microsoft Access is terrible with date formats, let alone partial dates, a
  `releases_release_year` column is added next to existing `releases_release_date`
  columns. This only lists the years, so comparison queries can be easily run against
  them as integers.

- Reduced the memory footprint by using multiple smaller JSON files instead of one big
  one.

- Fixed a bug where the rate limit was being interpreted as a string instead of an
  integer.

- Fixed a bug in the resume code.

- Fixed force restart not working as intended.

## v0.2 (20 August 2024)

Initial release
