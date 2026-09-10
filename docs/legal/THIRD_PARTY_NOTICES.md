# Third-Party Materials

The MIT license covers original software written for this repository. It does
not replace the terms attached to datasets, standards, papers, or third-party
packages.

## CICIoT2023

The experiment uses CICIoT2023 from the Canadian Institute for Cybersecurity,
University of New Brunswick. UNB states that its datasets may be redistributed,
republished, and mirrored when both the dataset and its listed research paper
are cited. The official source and required citation are recorded in
`docs/dataset/DATA_CARD.md`.

## NIST Publications

The included NIST publications are attributed to the National Institute of
Standards and Technology, U.S. Department of Commerce. NIST states that its
technical publications are generally public domain in the United States,
subject to separately marked third-party material. Files are included unchanged
and their official sources and hashes appear in `docs/standards/manifest.json`.

## IETF RFCs

RFC 8520 and RFC 8576 are complete, unchanged RFC Editor text files with their
notices preserved. The IETF Trust permits complete RFCs to be copied and
distributed under its Legal Provisions.

## ETSI EN 303 645

Copyright in ETSI standards belongs to ETSI, and reproduction requires
authorization. ETSI EN 303 645 V3.1.3 is therefore not committed here.
`scripts/bootstrap_inputs.py` downloads the unmodified document from the
official ETSI URL and verifies its expected SHA-256 hash locally.

Saved research records contain limited retrieved excerpts needed to audit the
reported evidence judgments. ETSI retains copyright in that material; its
appearance in an experiment record grants no license to reproduce the standard.

## Python Packages

Third-party Python dependencies are listed in `pyproject.toml` and
`requirements.lock.txt`. They retain their respective licenses.
