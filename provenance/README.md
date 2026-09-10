# Provenance

`experiment_environment_manifest.json` records the exact dataset archive hash,
standards URLs and hashes, frozen configuration, implementation hashes, Python
version, and operating system used for the reference experiment environment.

`release_manifest.json` is generated immediately before a public release and hashes every included file. It lists both the base proof-of-concept run IDs and the four journal run IDs. Verify the release with:

```bash
python scripts/reproduce.py verify
```

The original implementation hashes predate the public documentation and
cross-platform runner. They are retained so readers can distinguish scientific
experiment code from later release-only documentation improvements. The journal run directories contain their own model, cost, call, timing, and record-count provenance.
