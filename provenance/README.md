# Provenance

`experiment_environment_manifest.json` records the exact dataset archive hash,
standards URLs and hashes, frozen configuration, implementation hashes, Python
version, and operating system used for the reference experiment environment.

`release_manifest.json` is generated immediately before a public release and hashes every included file. It also lists the retained reference and evidence-gate run paths. Verify the release with:

```bash
python scripts/reproduce.py verify
```

The implementation hashes in `experiment_environment_manifest.json` were
captured with the reference environment before the public path cleanup. They
identify the code snapshot used for execution. The release manifest separately
hashes the current public files, while every retained run records its model,
cost, call, timing, and record-count provenance.
