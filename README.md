# xcloc-csv-converter

Small CLI tool to convert **Xcode localization exchange packages** (`.xcloc`) to **CSV** for translators, and to merge translated CSV back into a **copy** of the `.xcloc` for **Product → Import Localizations** in Xcode.

- **Python 3.10+**, **stdlib only** (no pip dependencies).
- Translations live in `Localized Contents/<locale>.xliff` only; `contents.json` and `Source Contents/**/*.xcstrings` are copied unchanged on import.

## CSV columns

| Column | Description |
|--------|-------------|
| **Key** | Base string key from the XLIFF `trans-unit` `id` (variant suffix stripped). |
| **Variant** | Suffix after `\|==\|` when present (e.g. `plural.one`, `device.other`). Empty for normal strings. |
| **Default (&lt;region&gt;)** | Source language text (from `contents.json` `developmentRegion`). |
| **&lt;Language&gt; (&lt;locale&gt;)** | Target translation for that locale. |
| **Comment** | Notes for translators (from XLIFF `<note>`). |
| **Source File** | Which catalog file the unit came from (e.g. `zndo/Localizable.xcstrings`). Required because the same key can appear in multiple files. |

Plural and device variants from the String Catalog appear as separate rows; the full XLIFF id is `Key|==|Variant`.

## Usage (run from this folder)

```bash
# Export an .xcloc (from Xcode: Product → Export Localizations) to CSV
python3 xcloc_converter.py to-csv path/to/zh-Hans.xcloc -o zh-Hans.csv

# Default output: <targetLocale>.csv in the current working directory if -o is omitted
python3 xcloc_converter.py to-csv path/to/zh-Hans.xcloc

# After translators fill the target column, produce a new .xcloc for import
python3 xcloc_converter.py to-xcloc zh-Hans.csv path/to/zh-Hans.xcloc -o path/to/zh-Hans-import.xcloc
```

Then in Xcode: **Product → Import Localizations…** and choose the generated `.xcloc`.

### Install as a command (optional)

From the repository root:

```bash
pip install .
```

This installs the `xcloc-csv` entry point (same CLI as `python3 xcloc_converter.py`).

## Behavior notes

- **Empty target cells** in the CSV are skipped; existing `<target>` entries in the template XLIFF are left as-is.
- **Non-empty targets** set or add `<target state="translated">…</target>`.
- Rewritten XLIFF may use an XML namespace prefix such as `ns0:` on elements; this is valid XML and is accepted by Xcode on import.

## License

Use and modify as needed for your project.
