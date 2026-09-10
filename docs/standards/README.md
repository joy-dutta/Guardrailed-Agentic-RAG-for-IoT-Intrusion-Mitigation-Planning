# Official Standards Retrieval Corpus

The RAG condition retrieves from seven official cybersecurity documents. These
documents provide evidence for the planner; they do not themselves implement
the deterministic guardrails.

| Document | Why it is in the corpus | Public packaging |
|---|---|---|
| NIST IR 8259A | Baseline IoT device cybersecurity capabilities | Included unchanged |
| NIST SP 800-213 | Guidance for applying IoT cybersecurity requirements | Included unchanged |
| NIST SP 800-213A | Detailed IoT device requirement catalog | Included unchanged |
| NIST SP 800-61 Rev. 3 | Incident-response and continuous-monitoring guidance | Included unchanged |
| ETSI EN 303 645 V3.1.3 | Consumer-IoT baseline security provisions | Downloaded locally from ETSI |
| RFC 8520 | Manufacturer Usage Description and network-access policy | Included unchanged |
| RFC 8576 | IoT threats and mitigations | Included unchanged |

Run the following from the repository root:

```bash
python scripts/reproduce.py bootstrap
```

The script checks every existing file against `manifest.json`. Missing files
are downloaded only from the recorded official URL. The ETSI document is not
redistributed because ETSI requires authorization for reproduction; the
bootstrap stage downloads and verifies it locally.

## Retrieval Configuration

- Parser: `pypdf` for PDF and UTF-8 for RFC text
- Chunk size: 1,400 characters
- Chunk overlap: 180 characters
- Index: TF-IDF with unigrams and bigrams
- Returned context: top three chunks
- Query inputs: predicted family and observed protocols only
- Delivered excerpt: centered on matched query terms

The reference corpus produced 666 chunks. Exact source URLs, expected
sizes, and SHA-256 hashes are in `manifest.json` and
`provenance/experiment_environment_manifest.json`.

NIST and IETF attribution and ETSI copyright details are recorded in
[`docs/legal/THIRD_PARTY_NOTICES.md`](../legal/THIRD_PARTY_NOTICES.md).
