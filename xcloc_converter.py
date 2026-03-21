#!/usr/bin/env python3
"""
Convert Xcode .xcloc localization bundles to CSV and back for translator workflows.

Uses only the Python standard library. Only Localized Contents/<locale>.xliff
carries translations; Source Contents and contents.json are copied unchanged on import.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import xml.etree.ElementTree as ET
from typing import Any

XLIFF_NS = "urn:oasis:names:tc:xliff:document:1.2"
XLIFF_NS_2 = "urn:oasis:names:tc:xliff:document:2.0"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

VARIANT_PREFIXES = ("plural.", "device.")

# Locale code -> English display name for CSV column headers
LOCALE_DISPLAY_NAMES: dict[str, str] = {
    "ar": "Arabic",
    "ca": "Catalan",
    "cs": "Czech",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fi": "Finnish",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "hr": "Croatian",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "ms": "Malay",
    "nb": "Norwegian Bokmål",
    "nl": "Dutch",
    "pl": "Polish",
    "pt-BR": "Portuguese, Brazil",
    "pt-PT": "Portuguese, Portugal",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sv": "Swedish",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "vi": "Vietnamese",
    "zh-Hans": "Chinese, Simplified",
    "zh-Hant": "Chinese, Traditional",
}


def _ns_tag(local: str) -> str:
    return f"{{{XLIFF_NS}}}{local}"


def locale_display_name(locale: str) -> str:
    return LOCALE_DISPLAY_NAMES.get(locale, locale)


def target_column_header(locale: str) -> str:
    return f"{locale_display_name(locale)} ({locale})"


def default_column_header(development_region: str) -> str:
    return f"Default ({development_region})"


def split_key_variant(trans_unit_id: str) -> tuple[str, str]:
    if "|==|" not in trans_unit_id:
        return trans_unit_id, ""
    key, variant = trans_unit_id.split("|==|", 1)
    return key, variant


def join_key_variant(key: str, variant: str) -> str:
    variant = (variant or "").strip()
    if not variant:
        return key
    return f"{key}|==|{variant}"


_warned_variants: set[str] = set()


def warn_unknown_variant(variant: str) -> None:
    if not variant:
        return
    ok = any(variant.startswith(p) for p in VARIANT_PREFIXES)
    if ok or variant in _warned_variants:
        return
    _warned_variants.add(variant)
    print(
        f"Warning: unknown variant suffix {variant!r} (expected plural.* or device.*).",
        file=sys.stderr,
    )


def load_contents_json(xcloc_path: str) -> dict[str, Any]:
    path = os.path.join(xcloc_path, "contents.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_xliff_path(xcloc_path: str, target_locale: str) -> str:
    localized = os.path.join(xcloc_path, "Localized Contents", f"{target_locale}.xliff")
    if os.path.isfile(localized):
        return localized
    raise FileNotFoundError(
        f"Expected XLIFF at {localized!r} (from contents.json targetLocale)."
    )


def element_text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return "".join(el.itertext())


def get_note_text(trans_unit: ET.Element) -> str:
    notes = trans_unit.findall(_ns_tag("note"))
    if not notes:
        return ""
    return "\n".join(element_text(n) for n in notes if element_text(n))


def validate_xliff_root(root: ET.Element) -> None:
    if root.tag != _ns_tag("xliff") and not root.tag.endswith("}xliff") and root.tag != "xliff":
        raise ValueError(f"Unexpected root element: {root.tag!r}")
    ver = root.get("version")
    if ver != "1.2":
        ns = root.tag.split("}")[0].strip("{") if "}" in root.tag else ""
        if ns == XLIFF_NS_2 or ver and ver.startswith("2"):
            sys.exit(
                "This tool only supports XLIFF 1.2. Found XLIFF 2.x or unknown version. "
                "Aborting to avoid corrupting the file."
            )
        print(
            f"Warning: expected xliff version='1.2', found {ver!r}. Continuing anyway.",
            file=sys.stderr,
        )


def count_groups(root: ET.Element) -> int:
    return len(root.findall(f".//{_ns_tag('group')}"))


def parse_trans_units(
    xliff_path: str,
) -> tuple[list[dict[str, str]], int, int]:
    tree = ET.parse(xliff_path)
    root = tree.getroot()
    validate_xliff_root(root)

    group_count = count_groups(root)
    if group_count:
        print(
            f"Warning: found {group_count} <group> element(s) in XLIFF. "
            "Current Xcode exports use flat <trans-unit> with |==| variant IDs; "
            "review manually if import seems incomplete.",
            file=sys.stderr,
        )

    rows: list[dict[str, str]] = []
    variant_entry_count = 0

    for file_el in root.findall(_ns_tag("file")):
        source_file = file_el.get("original") or ""
        body = file_el.find(_ns_tag("body"))
        if body is None:
            continue
        for tu in body.findall(_ns_tag("trans-unit")):
            full_id = tu.get("id") or ""
            key, variant = split_key_variant(full_id)
            if variant:
                variant_entry_count += 1
                warn_unknown_variant(variant)

            source_el = tu.find(_ns_tag("source"))
            source_text = element_text(source_el)

            target_el = tu.find(_ns_tag("target"))
            target_text = element_text(target_el) if target_el is not None else ""

            comment = get_note_text(tu)

            rows.append(
                {
                    "key": key,
                    "variant": variant,
                    "full_id": full_id,
                    "source": source_text,
                    "target": target_text,
                    "comment": comment,
                    "source_file": source_file,
                }
            )

    return rows, len(rows), variant_entry_count


def cmd_to_csv(args: argparse.Namespace) -> None:
    xcloc = os.path.abspath(args.xcloc)
    if not os.path.isdir(xcloc):
        sys.exit(f"Not a directory: {xcloc!r}")

    meta = load_contents_json(xcloc)
    if meta.get("version") != "1.0":
        print(
            f"Warning: contents.json version is {meta.get('version')!r}, expected '1.0'.",
            file=sys.stderr,
        )

    target_locale = meta["targetLocale"]
    development_region = meta.get("developmentRegion", "en")

    xliff_path = find_xliff_path(xcloc, target_locale)
    rows, total, variant_n = parse_trans_units(xliff_path)

    out_path = args.output
    if not out_path:
        out_path = os.path.join(os.getcwd(), f"{target_locale}.csv")

    target_hdr = target_column_header(target_locale)
    default_hdr = default_column_header(development_region)

    fieldnames = [
        "Key",
        "Variant",
        default_hdr,
        target_hdr,
        "Comment",
        "Source File",
    ]

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            quoting=csv.QUOTE_ALL,
        )
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "Key": r["key"],
                    "Variant": r["variant"],
                    default_hdr: r["source"],
                    target_hdr: r["target"],
                    "Comment": r["comment"],
                    "Source File": r["source_file"],
                }
            )

    print(
        f"Exported {total} trans-units ({variant_n} variant entries) from {xliff_path} -> {out_path}"
    )


def _resolve_csv_columns(
    headers: list[str],
    development_region: str,
    target_locale: str,
) -> dict[str, int]:
    """Map logical names to column indices."""
    default_hdr = default_column_header(development_region)
    target_hdr = target_column_header(target_locale)

    idx: dict[str, int] = {}
    lower = [h.strip() for h in headers]

    for i, h in enumerate(lower):
        if h == "Key":
            idx["key"] = i
        elif h == "Variant":
            idx["variant"] = i
        elif h == "Comment":
            idx["comment"] = i
        elif h == "Source File":
            idx["source_file"] = i
        elif h == default_hdr:
            idx["default"] = i
        elif h == target_hdr:
            idx["target"] = i

    # Fallback: match target column by suffix (locale)
    if "target" not in idx:
        suffix = f"({target_locale})"
        for i, h in enumerate(lower):
            if h.endswith(suffix) and "Default" not in h:
                idx["target"] = i
                break

    if "default" not in idx:
        for i, h in enumerate(lower):
            if h.startswith("Default (") and development_region in h:
                idx["default"] = i
                break

    required = ["key", "variant", "comment", "source_file", "target"]
    missing = [k for k in required if k not in idx]
    if missing:
        sys.exit(
            f"Could not resolve CSV columns {missing}. Headers: {headers!r}. "
            f"Expected Default column like {default_hdr!r} and target like {target_hdr!r}."
        )
    return idx


def load_csv_translations(
    csv_path: str,
    development_region: str,
    target_locale: str,
) -> dict[tuple[str, str], str]:
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return {}

        col = _resolve_csv_columns(header, development_region, target_locale)
        ik, iv, icom, isf, itgt = (
            col["key"],
            col["variant"],
            col["comment"],
            col["source_file"],
            col["target"],
        )

        out: dict[tuple[str, str], str] = {}
        for row in reader:
            if not row or all(not (c or "").strip() for c in row):
                continue

            def pad(j: int) -> str:
                return row[j] if j < len(row) else ""

            key = pad(ik).strip()
            variant = pad(iv).strip()
            source_file = pad(isf).strip()
            trans = pad(itgt)
            full_id = join_key_variant(key, variant)
            if trans.strip():
                out[(source_file, full_id)] = trans
        return out


def apply_translations_to_xliff(
    xliff_path: str,
    translations: dict[tuple[str, str], str],
) -> int:
    tree = ET.parse(xliff_path)
    root = tree.getroot()
    validate_xliff_root(root)

    updated = 0

    for file_el in root.findall(_ns_tag("file")):
        source_file = file_el.get("original") or ""
        body = file_el.find(_ns_tag("body"))
        if body is None:
            continue
        for tu in body.findall(_ns_tag("trans-unit")):
            full_id = tu.get("id") or ""
            key = (source_file, full_id)
            if key not in translations:
                continue
            text = translations[key]
            if not text.strip():
                continue

            target_el = tu.find(_ns_tag("target"))
            if target_el is None:
                # Insert after <source> if present, else at start of trans-unit
                source_el = tu.find(_ns_tag("source"))
                idx = 0
                if source_el is not None:
                    idx = list(tu).index(source_el) + 1
                target_el = ET.Element(_ns_tag("target"))
                target_el.set("state", "translated")
                target_el.text = text
                tu.insert(idx, target_el)
            else:
                target_el.set("state", "translated")
                target_el.text = text
            updated += 1

    # ElementTree cannot use default_namespace=XLIFF_NS on these files (conflicts with xml:space,
    # xsi:, etc.), so output uses an arbitrary prefix (often ns0:). This is valid XML and Xcode
    # accepts it for import.
    ET.register_namespace("xsi", XSI_NS)
    tree.write(xliff_path, encoding="UTF-8", xml_declaration=True)
    return updated


def cmd_to_xcloc(args: argparse.Namespace) -> None:
    csv_path = os.path.abspath(args.csv)
    xcloc_src = os.path.abspath(args.xcloc)
    out_xcloc = os.path.abspath(args.output)

    if not os.path.isfile(csv_path):
        sys.exit(f"CSV not found: {csv_path!r}")
    if not os.path.isdir(xcloc_src):
        sys.exit(f"Not a directory: {xcloc_src!r}")

    meta = load_contents_json(xcloc_src)
    if meta.get("version") != "1.0":
        print(
            f"Warning: contents.json version is {meta.get('version')!r}, expected '1.0'.",
            file=sys.stderr,
        )

    target_locale = meta["targetLocale"]
    development_region = meta.get("developmentRegion", "en")

    translations = load_csv_translations(csv_path, development_region, target_locale)
    if os.path.exists(out_xcloc):
        sys.exit(
            f"Output path already exists: {out_xcloc!r}. Remove it or choose another name."
        )

    shutil.copytree(xcloc_src, out_xcloc)

    xliff_dst = find_xliff_path(out_xcloc, target_locale)
    updated = apply_translations_to_xliff(xliff_dst, translations)

    print(f"Wrote {out_xcloc}: updated {updated} <target> element(s) in XLIFF.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert .xcloc bundles to/from CSV for localization workflows."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_csv = sub.add_parser("to-csv", help="Export .xcloc to CSV")
    p_csv.add_argument("xcloc", help="Path to .xcloc bundle")
    p_csv.add_argument(
        "-o",
        "--output",
        help="Output CSV path (default: <targetLocale>.csv in cwd)",
    )
    p_csv.set_defaults(func=cmd_to_csv)

    p_xcloc = sub.add_parser("to-xcloc", help="Apply CSV translations to a copy of .xcloc")
    p_xcloc.add_argument("csv", help="Input CSV path")
    p_xcloc.add_argument(
        "xcloc",
        help="Path to source .xcloc bundle (template; copied entirely)",
    )
    p_xcloc.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output .xcloc bundle path (must not exist)",
    )
    p_xcloc.set_defaults(func=cmd_to_xcloc)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
