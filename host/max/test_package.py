# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import build_package as bundle


class PackageTests(unittest.TestCase):
    def test_archive_is_repeatable_and_contains_exact_helper_bytes_and_help(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = (Path(temp) / name for name in ('first.zip', 'second.zip'))
            self.assertEqual(bundle.build(a), bundle.build(b))
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with zipfile.ZipFile(a) as archive:
                prefix = bundle.NAME + '/'
                manifest = json.loads(archive.read(prefix + 'bundle-manifest.json'))
                self.assertEqual(len(archive.namelist()), len(manifest['files_sha256']) + 1)
                for name, digest in manifest['files_sha256'].items():
                    self.assertEqual(hashlib.sha256(archive.read(prefix + name)).hexdigest(), digest)
                    self.assertFalse(Path(name).is_absolute())
                    self.assertNotIn('..', Path(name).parts)
                for name in bundle.SOURCES:
                    self.assertEqual(archive.read(prefix + 'patchers/' + name),
                                     (bundle.ROOT / 'host/max' / name).read_bytes())
                info = json.loads(archive.read(prefix + 'package-info.json'))
                self.assertIn(prefix + 'patchers/' + info['homepatcher'], archive.namelist())
                self.assertNotIn('filelist', info)
                self.assertEqual(archive.read(prefix+'patchers/rnbo.instrument.maxpat'),
                                 archive.read(prefix+'patchers/rnbo.studio.maxpat'))
                alias=json.loads(archive.read(prefix+'help/rnbo.instrument.maxhelp'))
                self.assertEqual(next(b['box']['name'] for b in alias['patcher']['boxes'] if b['box']['id']=='builder'),
                                 'rnbo.instrument.maxpat')
                help_patch = json.loads(archive.read(prefix + 'help/rnbo.studio.maxhelp'))
                source = json.loads(archive.read(prefix + 'patchers/embedded-sine.maxpat'))
                graph = lambda doc: next(b['box']['patcher'] for b in doc['patcher']['boxes'] if b['box']['id'] == 'rnbo')
                self.assertEqual(graph(help_patch), graph(source))

    def test_local_files_are_not_discovered_and_linked_sources_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'host/max').mkdir(parents=True)
            (root / 'LICENSES').mkdir()
            for name in bundle.SOURCES:
                (root / 'host/max' / name).write_bytes((bundle.ROOT / 'host/max' / name).read_bytes())
            (root / 'LICENSES/MIT.txt').write_bytes((bundle.ROOT / 'LICENSES/MIT.txt').read_bytes())
            (root / 'host/max/pairings.json').write_text('{"test-only-secret":"must-not-be-bundled"}')
            self.assertFalse(any('pairings' in name for name in bundle.collect(root)))
            target = root / 'host/max/rnbo-studio.js'
            target.unlink()
            target.symlink_to(bundle.ROOT / 'host/max/rnbo-studio.js')
            with self.assertRaisesRegex(ValueError, 'regular helper source'):
                bundle.collect(root)


if __name__ == '__main__':
    unittest.main()
