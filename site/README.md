# Object status website

Published at https://little-scale.github.io/esp32s3-rnbo/ by the repository's
`Publish object status` workflow. Only this directory is uploaded to Pages.
The website uses local HTML, CSS and JavaScript, with no external libraries.

The table contains 1,209 exact registered names/aliases in the pinned RNBO
1.4.4 inventory, 238 registry/guide codebox members/types/hooks, one unversioned
reference-only name, and seven separately labelled host/editor entries.
These 1,455 entries are not 1,455 independent DSP primitives. Gen, custom
packages and arbitrary user-defined functions are outside this inventory.

## Updating evidence

`data/inventory.json` preserves the metadata-only registry/reference audit.
`data/coverage.json` maps evidence to exact spellings and surfaces. Aliases and
codebox operations never inherit a patcher object's status automatically.
The original audit digest is retained in the coverage metadata; later additions
have their own source hashes. No generated RNBO implementation bodies are
included.

After qualifying an object, update its coverage record and source hashes.
Timings need explicit JSON pointers into committed evidence, equal vector counts,
matching module identities, and a separately attributed transformation. Identical
module controls cannot claim a speed gain. `PRIMARY_GROUPS` in the generator
selects representative aggregate results; it does not choose the fastest case.
Percentages are processing time saved for the stated fixture and reference,
not additive or universally applicable object speedups.

```sh
python3 tools/build_object_status.py
python3 tools/build_object_status.py --check
python3 -m unittest discover -s tools -p 'test_build_object_status.py' -v
node --check site/app.js
python3 -m http.server 8787 --directory site
```

Review the served page, search/filter controls, row details and evidence links.
Commit the source data and generated `data/status.json` together. The Pages
workflow rejects stale output or invalid timing evidence before deployment.
It requires no RNBO installation, credentials, private build artifacts or board.
