# Branch vs Combined Comparison Export

Generated for Google Sheets import.

## Files

| File | Use as Sheet tab |
|------|------------------|
| `01_config_comparison.csv` | Config (all sites) |
| `02_files_<site>.csv` | One tab per site — **Different**, **Missing in combined**, and **non-media Match** rows (matching images/assets excluded) |
| `03_all_files_comparison.csv` | All file diffs (master) |
| `04_summary_counts.csv` | Summary dashboard |

## Import to Google Sheets

1. Create a new Google Spreadsheet
2. File → Import → Upload each CSV
3. Choose **Insert new sheet(s)** for multi-file import
4. Apply filter + conditional formatting:
   - Green: Status = Match
   - Yellow: Status = Different
   - Red: Missing in combined / Missing in branch

## Comparison pairs

| Branch folder | Combined SITE_PROFILE |
|---------------|----------------------|
| Kupwara/ | kupwara |
| NCPass/ | ncpass |
| ganganagar/ | ganganagar |
| tangdhar/ | tangdhar |

## Regenerate

```bash
python3 generate_comparison.py
```

Run from the `BRANCH_COMPARISON/` directory (or pass the full path as above).

## Notes

- Config rows marked **Combined only** exist in `SITE_PROFILES` but not as direct keys in branch `__init__.py`. The **Branch value** column lists the helper/template files where that behavior lives in the branch.
- Re-run `python3 generate_comparison.py` after code changes to refresh
