# Changelog

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
