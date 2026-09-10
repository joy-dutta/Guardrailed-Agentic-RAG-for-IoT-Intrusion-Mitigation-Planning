# Technical Reproducibility Guide

`REPRODUCIBILITY_GUIDE.md` is the editable source. The corresponding PDF is a
professionally formatted handover document suitable for offline reading.

Rebuild it with:

```bash
python -m pip install -e ".[docs]"
python scripts/build_technical_guide.py
```

The guide describes the complete data lineage, calibration, confidence routing, 160-alert planning experiment, three retrieval conditions, deterministic guardrails, both evidence gates, GPT-5.6 Sol Ultra and Gemini Pro Extended reviews, cost controls, results, interpretation, and troubleshooting.

The generated file is `Technical_Reproducibility_Guide.pdf`.
