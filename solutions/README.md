# Solutions (Dataverse)

This folder holds **unpacked solution sources** for the three solutions that
make up the system. Source of truth for the schema and customizations lives
here, not in the cloud.

Layout (per solution):

```
B2BAgg.Core/
├── src/
│   ├── Entities/
│   ├── OptionSets/
│   ├── Roles/
│   ├── WebResources/
│   └── ...
└── Other/
    ├── Solution.xml
    └── Customizations.xml
```

## Workflow

```bash
# Authenticate to the right environment
pac auth select --name B2BAgg-Dev

# Export from Dev
pac solution export \
  --path solutions/B2BAgg.Core/B2BAgg_Core.zip \
  --name B2BAgg_Core \
  --managed false \
  --include general,autonumbering,calendar,customization,emailtracking,externalapplications,general,isvconfig,marketing,outlooksynchronization,relationshiproles,sales

# Unpack to source-friendly form for git
pac solution unpack \
  --zipfile solutions/B2BAgg.Core/B2BAgg_Core.zip \
  --folder solutions/B2BAgg.Core/src \
  --packagetype Unmanaged \
  --allowDelete true \
  --allowWrite true

# Reverse: pack and import (use in deploy workflows)
pac solution pack --folder solutions/B2BAgg.Core/src --zipfile B2BAgg_Core.zip --packagetype Managed
pac solution import --path B2BAgg_Core.zip
```

## Conventions

- One folder per solution: `B2BAgg.Core`, `B2BAgg.AI`, `B2BAgg.Integration`.
- `.zip` artifacts are gitignored; commit only the unpacked `src/` tree.
- Bump `Other/Solution.xml` version manually on each deploy
  (we'll automate this in MVP3).
