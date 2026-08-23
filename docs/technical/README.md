# Technical Reproducibility Guide

`REPRODUCIBILITY_GUIDE.md` is the editable source. The corresponding PDF is a
professionally formatted handover document suitable for offline reading.

Rebuild it with:

```bash
python -m pip install -e ".[docs]"
python scripts/build_technical_guide.py
```

The guide describes the full data lineage, method, execution order, canonical
run IDs, results, physical interpretation, limitations, and troubleshooting.

The generated file is `Technical_Reproducibility_Guide.pdf`.
