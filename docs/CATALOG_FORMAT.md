# Catalog format

## Inputs

- `data/custom_games.json`: JSON array of new game records or partial overrides.
- `data/addons.json`: JSON array of DLC, language packs, patches and other add-ons.
- Upstream source: `langegen/switch-games/switch_games.json`.

## Outputs

- `generated/catalog.json`: original records + local game records and overrides.
- `generated/addons.json`: local add-ons kept separate.

Local game records should follow upstream field names, such as `title`,
`title_id`, `version`, `cover`, and `description`. Keep any optional
fields used by the Switch client. A local game with the same `title_id` overrides
the upstream fields it supplies without deleting other upstream fields.

Add-ons use their own `title_id` and may use `base_title_id` to reference
their parent game. Suggested metadata fields: `title`, `title_id`,
`base_title_id`, `type` (dlc, language, update, other), `language`,
`version`, `description`, `cover`. Only include distribution URLs
for content you are authorized to distribute.

## Maintenance

1. Edit either data file as a valid JSON array.
2. Open **Actions > Update catalog > Run workflow** to publish.
3. Automatic sync also runs daily.
4. Git commit history provides rollback to earlier catalogs.

The current Switch client must be updated separately to read these new URLs.
The add-ons schema is a proposed contract, not yet guaranteed compatible with
the existing NRO. Do not delete the old source URL until the NRO is tested.
