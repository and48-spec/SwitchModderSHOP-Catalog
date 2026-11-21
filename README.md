# SwitchModderSHOP Catalog

Independent, versioned catalog for SwitchModderSHOP.

## Catalog endpoints

- Games: [generated/catalog.json](generated/catalog.json)
- Add-ons and language packs: [generated/addons.json](generated/addons.json)

**Note:** The generated files appear after the first successful workflow run.
The current NRO still needs an explicit change to consume this repository.

## Architecture

- Original upstream JSON is downloaded during each sync, without changing the original project.
- `data/custom_games.json` stores locally managed games and metadata overrides.
- `data/addons.json` stores DLC, language packs, and updates independently.
- `scripts/sync_catalog.py` validates and merges data.
- GitHub Actions runs daily or manually, only committing when output changes.
- Git history preserves previous versions and allows rollback.

## First publication

Open the **Actions** tab, select **Update catalog**, then **Run workflow**
on the `main` branch. Check its logs if the original provider changed its JSON format.

## Manual updates

Edit `data/custom_games.json` or `data/addons.json` directly on GitHub,
commit changes, then run the workflow. Keep only content you are allowed
to distribute or link to.

See [Catalog format](docs/CATALOG_FORMAT.md) for schema guidelines.

## Planned integration

The Windows Catalog Manager can edit the input files and trigger publishing;
the Switch client can request the generated endpoints and show related add-ons.
These client integrations are not yet included in this repository.
