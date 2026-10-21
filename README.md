# Calcelyx 1.0

Calcelyx is an offline Windows application for preparing renovation and interior-finishing estimates. It does not require an internet connection or Microsoft Excel.

[Polska wersja README](README_PL.md)

## Main features

- client, project and room management;
- manual room entry with separate door and window dimensions;
- automatic floor, ceiling, wall and baseboard measurements;
- polygonal floor-plan tracing;
- PDF, JPG and PNG backgrounds;
- scale calibration from two known points;
- zoom with `Ctrl+mouse wheel`, panning and undo/redo;
- an editable price list managed in the app or Excel;
- validated Excel price-list import;
- waste, difficulty multipliers, minimum charges, markup, discount and VAT;
- manually entered travel distance, visits, parking and travel cost;
- customer-facing PDF quotes and detailed Excel estimates;
- local SQLite storage, immutable estimate revisions and backups;
- English and Polish interface selected in `Settings`.
- Per-project currency selected in `Settings` (PLN, EUR, USD, GBP, CHF, CZK, SEK, NOK or DKK).

## Running the packaged application

1. Download `Calcelyx-1.0-Windows.zip` from the latest GitHub release.
2. Extract the entire archive to a writable folder.
3. Run `Calcelyx.exe` and keep it together with the `_internal` folder.

When building from source, the same application folder is created at `dist/Calcelyx`.

The application stores user data beside the executable in `Dane`, `Eksporty` and `Kopie_zapasowe`. These folders are created only when the application is used and are not part of the public source package.

## Language

English is the default language. Open `Settings`, find `Application language`, and select `Polski` to switch the interface and exported documents to Polish. The choice is saved locally.

The estimate currency is configured separately under `Settings` → `Quote rules`. It changes amounts shown in the application and in newly exported PDF and Excel files. Existing projects without a saved currency use PLN.

Custom room names, client data and imported service descriptions are never automatically translated.

## Editable price lists

Two equivalent example workbooks are included:

- `data/Calcelyx_Price_List_EN.xlsx` — English;
- `data/Calcelyx_Cennik_PL.xlsx` — Polish.

The amounts are illustrative and are not verified market prices. Replace them with your own company rates before preparing a real quote. Keep the item codes and required column names unchanged. The importer reports invalid rows and does not replace the active price list until the entire workbook passes validation.

## Tracing a PDF floor plan

1. Open `Plan & measurements`.
2. Select `Open PDF / image`.
3. Use `Fit page`. Zoom with `Ctrl+mouse wheel`; pan with the middle mouse button or `Pan` mode.
4. Select `Calibrate scale` and click the two endpoints of a known dimension.
5. Enter the actual distance in meters.
6. Draw the property's main outline. Clicking point 1 closes the polygon exactly at its starting point.
7. Select `+ Room` for each room, enter its name and draw a separate outline.
8. Save a closed room outline with `Save as room`. `Ctrl+Z` and `Ctrl+Y` undo and redo changes.

The background is intended for manual tracing. Calcelyx does not automatically interpret walls or dimensions from construction documents.

## Important limitations

- Calcelyx does not determine the legally correct VAT rate.
- A contractor should verify all measurements, rates and scope before issuing a quote.
- Create a backup before importing a large or materially changed price list.
- Save a separate revision whenever a quote is sent to or accepted by a client.

## Running from source

Python 3.11 is recommended.

```text
python -m pip install -r requirements.txt
run_dev.cmd
```

Run the automated tests:

```text
set PYTHONPATH=src
python -m pytest -q
```

Calcelyx is released under the MIT License. Third-party components and their licenses are listed in `THIRD-PARTY-NOTICES.txt` and included in packaged releases.

