# CICIoT2023 Data Card

## Source

This project uses the official CICIoT2023 CSV release from the Canadian
Institute for Cybersecurity at the University of New Brunswick:

- Dataset page: <https://www.unb.ca/cic/datasets/iotdataset-2023.html>
- Archive used: `CSV.zip`, stored locally as `data/raw/CICIoT2023_CSV.zip`
- Size: 1,430,268,604 bytes
- SHA-256: `E211E878D2F39226EA3A854683F91AE6175B628807EE96EEECB7A04A36A28DBD`
- Source files: 309 CSV files
- Source rows: 46,776,700
- Numerical columns: 39

Required dataset citation:

> E. C. P. Neto, S. Dadkhah, R. Ferreira, A. Zohourian, R. Lu, and A. A.
> Ghorbani, "CICIoT2023: A Real-Time Dataset and Benchmark for Large-Scale
> Attacks in IoT Environment," Sensors, vol. 23, no. 13, 2023,
> doi:10.3390/s23135941.

The PDF distributed with the CSV archive is preserved as
`CICIoT2023_README_CSV.pdf`.

## What One Row Means

One row is a numerical traffic observation produced by the dataset's feature
extraction process. It is not a complete incident, a unique physical device, or
proof that a particular device is compromised. The CSV rows contain no label or
verified device identifier. The source folder supplies the attack type.

For this reason, the planner uses an observed flow-profile scope. It does not
invent a device identity or claim device-specific enforcement.

## Mapping 34 Attack Types to Eight Families

The complete machine-readable mapping is
`reports/tables/attack_family_mapping.csv`.

| Broad family | Included official attack types |
|---|---|
| Benign | Benign_Final |
| BruteForce | DictionaryBruteForce |
| DDoS | ACK fragmentation, HTTP, ICMP, PSH-ACK, RST-FIN, SYN, SlowLoris, synonymous-IP, TCP, UDP, and UDP-fragmentation DDoS variants |
| DoS | HTTP, SYN, TCP, and UDP DoS variants |
| Mirai | greeth flood, greip flood, and udpplain |
| Recon | host discovery, OS scan, ping sweep, and port scan |
| Spoofing | DNS spoofing and MITM ARP spoofing |
| Web | backdoor malware, browser hijacking, command injection, SQL injection, uploading attack, vulnerability scan, and XSS |

The broader families make the mitigation policy understandable and leave enough
examples per class for calibration and evaluation. They are analytical groups,
not claims that all attack types inside a family are operationally identical.

## Preparation

The code samples up to 60,000 rows per family using seed `20260821`, converts
infinite values to missing values, median-imputes missing values inside the
model pipeline, and removes duplicate feature vectors across splits. The fixed
prepared sample contains 378,527 rows.

The primary detector excludes `Number` and `Tot sum`. These fields describe the
aggregation window and were found to be characteristic of source collection
folders. Keeping them can let a model recognize collection behavior instead of
network behavior. The all-feature result remains available as an ablation.

## Three Split Protocols

| Protocol | Purpose | Main caution |
|---|---|---|
| `stratified_rows` | Optimistic reference with family-stratified rows | Rows from one source file can cross splits |
| `attack_type_aware` | Primary PoC protocol; keeps all 34 attack types represented | Rare types with fewer than three files require deterministic row blocks |
| `strict_family_file` | Whole-file distribution-shift stress test | Rare subtypes can occur in only one split |

The selected attack-type-aware split contains 221,795 training rows, 78,133
calibration rows, and 78,599 test rows. Test labels do not select the confidence
threshold.

## Fixed Agent Cases

Four test cases are selected per true family: two confident correct predictions,
one low-confidence correct prediction, and the highest-confidence error. This
creates 32 fixed alerts. The LLM receives the detector prediction, calibrated
confidence, route, flow-profile scope, and selected features. It does not
receive the hidden ground-truth family.

The exact cases are stored in
`data/processed/agent_cases_attack_type_aware.jsonl`.

## Data Limitations

- Rows are offline observations, not live incidents.
- No verified device identity is available.
- Traffic from the same data-generation environment can share collection
  characteristics.
- Strict unseen-file evaluation is harder and more variable than the primary
  protocol.
- Detector performance cannot establish whether a mitigation action suppresses
  an attack or preserves benign service.
