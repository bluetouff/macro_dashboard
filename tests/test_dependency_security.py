"""Offline security regressions for the pinned runtime and its TLS bundles."""

from __future__ import annotations

import hashlib
import io
import re
import ssl
import tempfile
import unittest
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
from pathlib import Path

import certifi
import requests.certs
from packaging.version import Version
from PIL import Image
from pip._vendor import certifi as pip_certifi
from streamlit.elements.lib.image_utils import _ensure_image_size_and_format
from streamlit.elements.lib.layout_utils import LayoutConfig

ROOT = Path(__file__).resolve().parents[1]
MINIMUM_VERSIONS = {
    'certifi': '2026.10.19',
    'filelock': '4.2.1',
    'GitPython': '3.2.1',
    'pillow': '13.0.0',
    'pip': '26.2.2',
    'setuptools': '84.1.0',
    'streamlit': '1.66.1',
}


class DependencySecurityTests(unittest.TestCase):
    @unittest.skipUnless(find_spec('filelock') and find_spec('cachecontrol'), 'Development audit cache only')
    def test_filelock_preserves_audit_cache_write_and_read(self) -> None:
        from cachecontrol.caches.file_cache import FileCache

        with tempfile.TemporaryDirectory() as directory:
            cache = FileCache(directory)
            cache.set('local-fixture', b'cache-entry')
            self.assertEqual(cache.get('local-fixture'), b'cache-entry')
            cache.delete('local-fixture')
            self.assertIsNone(cache.get('local-fixture'))

    def test_pins_and_installed_packages_meet_security_floors(self) -> None:
        pins = dict(re.findall(r'^([^#\s=]+)==([^\s]+)$', (ROOT / 'constraints.txt').read_text(), re.MULTILINE))
        for name, minimum in MINIMUM_VERSIONS.items():
            with self.subTest(package=name):
                self.assertGreaterEqual(Version(pins[name]), Version(minimum))
                try:
                    installed = version(name)
                except PackageNotFoundError:
                    # filelock is used by the development audit tools, not the app.
                    self.assertEqual(name, 'filelock')
                else:
                    self.assertEqual(installed, pins[name])

    def test_compromised_root_is_absent_from_requests_and_pip_bundles(self) -> None:
        compromised = '86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b'
        self.assertEqual(requests.certs.where(), certifi.where())
        for bundle in (certifi.where(), pip_certifi.where()):
            with self.subTest(bundle=bundle):
                certificates = re.findall(
                    r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----',
                    Path(bundle).read_text(encoding='ascii'), re.DOTALL,
                )
                self.assertTrue(certificates)
                fingerprints = {
                    hashlib.sha256(ssl.PEM_cert_to_DER_cert(certificate)).hexdigest()
                    for certificate in certificates
                }
                self.assertNotIn(compromised, fingerprints)

    def test_pillow_and_streamlit_preserve_local_image_encoding(self) -> None:
        for format in ('PNG', 'JPEG'):
            with self.subTest(format=format):
                output = io.BytesIO()
                Image.new('RGB', (8, 4), color=(25, 100, 150)).save(output, format=format)
                encoded = _ensure_image_size_and_format(output.getvalue(), LayoutConfig(width=4), format)
                with Image.open(io.BytesIO(encoded)) as decoded:
                    decoded.load()
                    self.assertEqual(decoded.size, (4, 2))
                    self.assertEqual(decoded.format, format)
