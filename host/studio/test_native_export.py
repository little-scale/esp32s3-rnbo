# SPDX-License-Identifier: MIT
import base64
import io
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from host import native_export as n


def fixture():
    return {'instrument.h': b'template <typename Engine> class rnbomatic : public Engine {};',
            'description.json': b'{}', 'dependencies.json': b'[]',
            'common/RNBO_Version.h': b'const char * version = "1.4.4";',
            'common/RNBO_Common.h': b'// matching runtime'}


def payload(files=None):
    return {'name':'example', 'export_files':[{'path':name,'data_base64':base64.b64encode(raw).decode()}
        for name, raw in (fixture() if files is None else files).items()]}


def zip_payload(entries):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in entries: archive.writestr(name,raw)
    return {'zip_base64':base64.b64encode(out.getvalue()).decode()}


class NativeExportTests(unittest.TestCase):
    def test_folder_and_nested_zip_preserve_generated_bytes_and_find_class(self):
        for data in (payload(),zip_payload([('Export/'+name,raw) for name,raw in fixture().items()])):
            files, classname=n.normalise(n.unpack(data))
            self.assertEqual(classname,'rnbomatic')
            self.assertEqual(files['rnbo_source.h'],fixture()['instrument.h'])
            self.assertEqual(files['common/RNBO_Common.h'],fixture()['common/RNBO_Common.h'])
            self.assertIn('RNBO-runtime-LICENSE',files)
            with tempfile.TemporaryDirectory() as temp:
                out=Path(temp)/'normalised';n.write(files,out)
                self.assertEqual((out/'rnbo_source.h').read_bytes(),fixture()['instrument.h'])
                with self.assertRaises(FileExistsError):n.write(files,out)

    def test_path_traversal_links_duplicates_and_invalid_encoding_reject(self):
        for name in ('../outside.h','/absolute','a/../b','a//b','a\\b','C:/a','a/./b'):
            with self.subTest(name=name),self.assertRaises(ValueError):n.unpack(payload({name:b'x'}))
        duplicate=payload();duplicate['export_files']*=2
        with self.assertRaisesRegex(ValueError,'Duplicate'):n.unpack(duplicate)
        bad=payload();bad['export_files'][0]['data_base64']='!!!!'
        with self.assertRaises(ValueError):n.unpack(bad)
        link=zipfile.ZipInfo('link.h');link.create_system=3;link.external_attr=(stat.S_IFLNK|0o777)<<16
        with self.assertRaisesRegex(ValueError,'Linked'):n.unpack(zip_payload([(link,b'../outside')]))
        with self.assertRaises(ValueError):n.unpack(zip_payload([('../outside',b'x')]))
        with self.assertRaisesRegex(ValueError,'Duplicate'):n.unpack(zip_payload([('a',b'1'),('a',b'2')]))

    def test_expanded_size_and_multiple_export_roots_reject(self):
        from unittest.mock import patch
        data=zip_payload([('a',b'x'*100)])
        with patch.object(n,'MAX_BYTES',50),self.assertRaises(ValueError):n.unpack(data)
        for changed in ({'second/description.json':b'{}'}, {'sample.wav':b'asset'},
                        {'dependencies.json':b'[{"asset":"sample.wav"}]'},
                        {'common/RNBO_Version.h':b'const char * version = "1.4.6";'},
                        {'second.h':fixture()['instrument.h']}):
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                n.normalise(dict(fixture(),**changed))

    def test_optional_drawing_is_never_executable_input(self):
        from host.studio.server import build_settings
        value=build_settings(dict(payload(),visual_patch={'patcher':{'boxes':[],'lines':[]}}))
        self.assertEqual(value['class_name'],'rnbomatic')
        self.assertNotIn('numerical_profile',value)
        self.assertEqual(value['export_files']['rnbo_source.h'],fixture()['instrument.h'])
        with self.assertRaisesRegex(ValueError,'Max'):build_settings({'patch':{'patcher':{}}})
        for name in ('voices','numerical_profile','float32_delays','filter_delay_max_ms'):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'retired'):
                build_settings(dict(payload(),**{name:None}))

    def test_copy_library_runtime_sources_and_mac_zip_metadata_are_accepted(self):
        files=dict(fixture(),**{'common/RNBO_ListU.cpp':b'// copied, not compiled', '__MACOSX/._instrument.h':b'noise'})
        result,_=n.normalise(n.unpack(payload(files)))
        self.assertEqual(result['common/RNBO_ListU.cpp'],files['common/RNBO_ListU.cpp'])
        self.assertNotIn('__MACOSX/._instrument.h',result)
