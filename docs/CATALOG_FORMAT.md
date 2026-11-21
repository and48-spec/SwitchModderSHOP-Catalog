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

Add-ons are stored separately and linked to a game using `parent_title_id`.
Each add-on requires `title`, `parent_title_id`, and `content_type`
(`dlc`, `language`, `update`, or `other`). Optional fields include
`title_id`, `language`, `version`, `description`, `cover`, and `url`.
The older input aliases `base_title_id` and `type` are accepted but
converted to the canonical fields in `generated/addons.json`.

Example metadata-only language pack record:

```json
[
  {
    "title": "Italian language pack (example)",
    "parent_title_id": "0100000000000000",
    "content_type": "language",
    "language": "it",
    "description": "Example only; replace with a real, verified title ID"
  }
]
```

The example ID above is a placeholder, not a verified game identifier.
Only include links to content you are authorized to distribute. The
add-ons file is not yet consumed by the NRO; the console detail UI must
be enhanced to display content linked to `parent_title_id`.

## Maintenance

1. Edit either data file as a valid JSON array.
2. Open **Actions > Update catalog > Run workflow** to publish.
3. Automatic sync also runs daily.
4. Git commit history provides rollback to earlier catalogs.

The current Switch client must be updated separately to read these new URLs.
The add-ons schema is a proposed contract, not yet guaranteed compatible with
the existing NRO. Do not delete the old source URL until the NRO is tested.
