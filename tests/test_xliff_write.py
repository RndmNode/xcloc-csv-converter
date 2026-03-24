"""Regression: XLIFF output must match Xcode's default-namespace form (no ns0: prefix)."""

import tempfile
import unittest
from pathlib import Path

import xml.etree.ElementTree as ET

import xcloc_converter as xc

MINIMAL_XLIFF = """<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.2" xsi:schemaLocation="urn:oasis:names:tc:xliff:document:1.2 http://docs.oasis-open.org/xliff/v1.2/os/xliff-core-1.2-strict.xsd">
  <file original="zndo/Localizable.xcstrings" source-language="en" target-language="zh-Hans" datatype="plaintext">
    <header>
      <tool tool-id="com.apple.dt.xcode" tool-name="Xcode" tool-version="26.0" build-num="1"/>
    </header>
    <body>
      <trans-unit id="hello" xml:space="preserve">
        <source>Hello</source>
        <note>A greeting</note>
      </trans-unit>
    </body>
  </file>
</xliff>
"""


class TestXliffWrite(unittest.TestCase):
    def test_apply_translations_writes_unprefixed_xliff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "zh-Hans.xliff"
            p.write_text(MINIMAL_XLIFF, encoding="utf-8")
            n = xc.apply_translations_to_xliff(
                str(p),
                {("zndo/Localizable.xcstrings", "hello"): "你好"},
            )
            self.assertEqual(n, 1)
            out = p.read_text(encoding="utf-8")
            self.assertNotIn("ns0:", out)
            self.assertIn('<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2"', out)
            self.assertRegex(out, r'^<\?xml version="1\.0" encoding="UTF-8"\?>')
            root = ET.fromstring(out)
            self.assertTrue(
                root.tag.endswith("}xliff") or root.tag == "xliff",
                root.tag,
            )

    def test_normalize_idempotent_for_default_ns(self) -> None:
        s = MINIMAL_XLIFF.strip()
        self.assertEqual(xc._normalize_xliff_xml_for_xcode(s), s)


if __name__ == "__main__":
    unittest.main()
