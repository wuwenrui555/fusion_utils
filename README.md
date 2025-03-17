# fusion_utils

Compatible for PhenoCycle Experiment Designer (V2.1.0).

- `generate_fusion_xpd`: generate an `.xpd` file according to a given CODEX panel.

## generate_fusion_xpd

```sh
generate_fusion_xpd --param "/path/to/input_param.json"
```

### `.json` for input parameters

```json
{
  "xpd_f": "data/raw/test_final.xpd",
  "excel_f": "data/raw/codex_marker.xlsx",
  "output_f": "data/output/test_final.xpd",
  "start_well": "C1",
  "channel_1": "ATTO550",
  "channel_2": "CY5"
}
```

- `xpd_f`: path to newly created `.xpd` file with only BLANK wells.
- `excel_f`: path to `.xlsx` file with CODEX panel information.
- `output_f`: path to output `.xpd` file.
- `start_well`: well name of the start well.
- `channel_1`: channel name of the first piece of CODEX panel information.
- `channel_2`: channel name of the second piece of CODEX panel information.

### `.xlsx` for CODEX panel

- Cycle number (starts from 0)
  - **`(00, A) Cycle` #**
- The first piece of information:
  - **`(01, B) Cy3 (channel_1)` #** (`markerName` in `.xpd`)
  - **`(02, C) Oligo` #** (`reporter` in `.xpd`)
  - **`(03, D) CID` #** (`barcode` in `.xpd`)
  - **`(04, E) Clone` #** (`clone` in `.xpd`)
  - `(05, F) Stock Concentration`
  - `(06, G) Desired Concentration`
  - `(07, H) Volume for 70µl`
  - **`(08, I) msec` #** (`exposure` in `.xpd`)
  - `(09, J) Comments`
- The second piece of information:
  - **`(10, K) Cy5 (channel_2)` #**
  - **`(11, L) Oligo` #**
  - **`(12, M) CID` #**
  - `(14, O) Stock Concentration`
  - `(15, P) Desired Concentration`
  - `(16, Q) Volume for 70µl`
  - **`(17, R) msec` #**
  - `(18, S) Comments`

Only columns with `#` are necessary. The columns needed are select using the index of columns, so the index of columns should be correct (`[index started from 0], [column name in Microsoft Excel]`). For those unnecessary columns, empty columns can be used as space holders.
