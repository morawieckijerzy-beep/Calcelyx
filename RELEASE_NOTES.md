# Calcelyx 1.0.1

Maintenance release with fixes for data-loss and calculation bugs found in a code review (pull request #1). Upgrading from 1.0 is recommended.

## Fixes

- Saving a project no longer deletes files outside the projects folder.
- Opening a project is transactional: a failed open leaves the current project untouched.
- Unreadable autosaves and rejected price-list rows are kept instead of being silently discarded.
- The application window and the PDF quote now use one shared totals calculation, so the amounts always match.
- The line editor keeps exact prices instead of rounded display values.
- Undo/redo history is cleared when switching projects.
- Estimate revision status rules are enforced.
- The database copy stores the full project.

## Installation

1. Download `Calcelyx-1.0.1-Windows.zip` from the GitHub release.
2. Extract the entire archive to a writable folder (do not overwrite the 1.0 folder if you want to keep it as a backup).
3. Run `Calcelyx.exe`; do not move the executable away from its `_internal` folder.

User data lives beside the executable in `Dane`, `Eksporty` and `Kopie_zapasowe`. To keep existing projects, copy these folders from the 1.0 folder into the new one before first launch.

## Verification

The automated test suite contains 92 passing tests.

---

# Calcelyx 1.0

First public Windows release of Calcelyx, an offline estimator for renovation and interior-finishing work.

Calcelyx was conceived and directed by **Jerzy Morawiecki**. The software implementation, technical design, tests and documentation were produced with **OpenAI Codex** under his direction and iterative review.

## Highlights

- English and Polish interface.
- Project-specific currencies: PLN, EUR, USD, GBP, CHF, CZK, SEK, NOK and DKK.
- Manual rooms, doors and windows with calculated floor, ceiling, wall and baseboard measurements.
- PDF/JPG/PNG plan backgrounds with scale calibration, room outlines, zoom, pan and undo/redo.
- Editable price list in the application or Excel.
- Estimate items assigned to rooms, travel costs, VAT, markup, discount and revisions.
- PDF quote and Excel estimate exports.
- Fully offline local storage and backups.

## Installation

1. Download `Calcelyx-1.0-Windows.zip` from the GitHub release.
2. Extract the entire archive to a writable folder.
3. Run `Calcelyx.exe`; do not move the executable away from its `_internal` folder.

Windows may display a SmartScreen warning because this community build is not code-signed.

## Verification

The automated test suite contains 39 passing tests. The included test report documents the manual and standards-inspired review. Example price-list values are illustrative and must be replaced before preparing real quotations.
