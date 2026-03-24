# xcloc-csv-converter

Small CLI tool to convert **Xcode localization exchange packages** (`.xcloc`) to **CSV** for translators, and to merge translated CSV back into a **copy** of the `.xcloc` for **Product → Import Localizations** in Xcode.

- **Python 3.10+**, **stdlib only** (no pip dependencies).
- Translations live in `Localized Contents/<locale>.xliff` only; `contents.json` and `Source Contents/**/*.xcstrings` are copied unchanged on import.

## CSV columns

| Column | Description |
|--------|-------------|
| **Key** | Base string key from the XLIFF `trans-unit` `id` (variant suffix stripped). |
| **Variant** | Suffix after `\|==\|` when present (e.g. `plural.one`, `device.other`). Empty for normal strings. |
| **Default (<region>)** | Source language text (from `contents.json` `developmentRegion`). |
| **<Language> (<locale>)** | Target translation for that locale. |
| **Comment** | Notes for translators (from XLIFF `<note>`). |
| **Source File** | Which catalog file the unit came from (e.g. `zndo/Localizable.xcstrings`). Required because the same key can appear in multiple files. |

Plural and device variants from the String Catalog appear as separate rows; the full XLIFF id is `Key|==|Variant`.

## Usage (round trip)

This is the typical workflow if you want to go from a `.xcloc` bundle → CSV → edited translations → new `.xcloc` bundle:

- Export or obtain a `.xcloc` bundle (a directory, usually named `Something.xcloc`).
- Run `to-csv` to generate a CSV translators can edit.
- Translate by filling in the **target-language column** (for example `Chinese, Simplified (zh-Hans)`).
- Run `to-xcloc` to create a **new** `.xcloc` bundle that contains those translations.
- Import the new bundle in Xcode: **Product → Import Localizations…**

## Usage (commands)

```bash
# Export an .xcloc (from Xcode: Product → Export Localizations) to CSV
python3 xcloc_converter.py to-csv path/to/zh-Hans.xcloc -o zh-Hans.csv

# Default output: <targetLocale>.csv in the current working directory if -o is omitted
python3 xcloc_converter.py to-csv path/to/zh-Hans.xcloc

# After translators fill the target column, produce a NEW .xcloc for import.
# The output path must not exist (the tool refuses to overwrite).
python3 xcloc_converter.py to-xcloc zh-Hans.csv path/to/zh-Hans.xcloc -o path/to/zh-Hans-import.xcloc
```

Then in Xcode: **Product → Import Localizations…** and choose the generated `.xcloc`.

### CSV → `.xcloc` expectations (important)

- The CSV should come from `to-csv` (or at least keep compatible headers). The tool resolves columns based on headers like `Key`, `Variant`, `Comment`, `Source File`, plus `Default (<developmentRegion>)` and `<Language> (<targetLocale>)`.
- Rows are matched by **Source File + Key/Variant** (so keep the `Source File` column intact).
- Only **non-empty** cells in the target-language column are applied; empty target cells are skipped.
- Use the **same** `.xcloc` you exported to CSV (or an equivalent export from the same project revision) as the template for `to-xcloc`. A CSV from a different export can break column paths or keys even though `Source Contents/**/*.xcstrings` is still copied unchanged.

### Troubleshooting Xcode import

- **`Source Contents`**: `to-xcloc` copies the entire template bundle; string catalogs under `Source Contents/` are not modified. If Xcode complains about catalogs, check that you are importing into the project named in `contents.json` and that your CSV was produced from a matching bundle.
- **XLIFF**: The tool writes `Localized Contents/<locale>.xliff` in the same default-namespace style as Xcode exports (not ElementTree’s `ns0:` prefix), so the importer can read the file reliably.

### Install as a command (optional)

From the repository root:

```bash
pip install .
```

This installs the `xcloc-csv` entry point (same CLI as `python3 xcloc_converter.py`).

## Behavior notes

- **Empty target cells** in the CSV are skipped; existing `<target>` entries in the template XLIFF are left as-is.
- **Non-empty targets** set or add `<target state="translated">…</target>`.
- **XLIFF on disk** is normalized after editing so it matches Xcode’s default-namespace XLIFF (not a prefixed `ns0:` rewrite), which avoids import issues with Xcode’s localization importer.

## License

Use and modify as needed for your project.
