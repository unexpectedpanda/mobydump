# Changelog

## v0.3 (25 August 2024)

- Extra game details are now pulled from the `/games/{game_id}/platforms/{platform_id}`
  endpoint after the initial details have been pulled from
  `/games?platform={platform_id}`. This is necessarily slow, as you can only request one
  game at a time, unlike `/games?platform={platform_id}` which returns 100 games at a
  time. This, in combination with a 5 second MobyPro rate limit means completing the DOS
  set, which has 8,461 titles at the time of writing, will take just under 12 hours.
  Double that if you're using the free API key.

  It'd be significantly more efficient if MobyGames included the single game endpoint
  data in the `/games?platform={platform_id}` response, but sadly it isn't so.

- You can now set the rate limit in the `.env` file, so you don't need to add the command
  line argument each time.

- MobyDump now only shows the release date for the selected platform. Other platforms are
  no longer displayed.

- Alternate titles are no longer concatenated into the one field, and have been moved to
  the end of the dataset. Unfortunately many of these titles aren't platform-specific,
  but they're difficult to weed out as they aren't paired with platform IDs.

- Removed the following columns from the export:

  - MobyGames score and number of votes

  - Screenshot and cover images

- A bug has been fixed where the rate limit was being interpreted as a string instead of
  an integer.

## v0.2 (20 August 2024)

Initial release
