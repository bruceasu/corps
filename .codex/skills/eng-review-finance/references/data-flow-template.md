# Data Flow Template

```text
Source System
  -> ingestion / ETL / stream processor
  -> warehouse / mart / operational store
  -> service API
  -> admin UI / dashboard / report
```

## Data Flow Table
| Step | Input | Processing | Output | Owner | Failure Mode | Validation |
|---|---|---|---|---|---|---|

## Data Freshness
| Dataset | Expected Refresh | SLA | Alert Threshold |
|---|---|---|---|

## Data Quality
| Check | Rule | Severity | Owner |
|---|---|---|---|
