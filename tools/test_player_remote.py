# SPDX-License-Identifier: MIT
from pathlib import Path
import gzip,os,re,shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class RemoteTests(unittest.TestCase):
    def compile_run(self,source,expected,transport=False):
        idf=Path(os.environ.get('IDF_PATH',str(Path.home()/'esp/esp-idf')));json=idf/'components/json/cJSON'
        if not shutil.which('cc') or not (json/'cJSON.c').is_file():
            self.skipTest('A host C compiler and installed ESP-IDF cJSON source are required')
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'test'
            result=subprocess.run(['cc','-std=c11','-D_POSIX_C_SOURCE=200809L','-O1','-Wall','-Wextra','-Werror',
                '-fsanitize=undefined,bounds','-fno-sanitize-recover=all',
                *(['-I'+str(ROOT/'tests/remote/stubs')] if transport else []),
                '-I'+str(ROOT/'firmware/components/player_remote/include'),'-I'+str(ROOT/'module-sdk/include'),'-I'+str(json),
                str(ROOT/source),str(ROOT/'firmware/components/player_remote/player_remote_core.c'),str(json/'cJSON.c'),'-lm','-o',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(out)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn(expected,result.stdout)
    def test_actual_parser_and_schema(self):self.compile_run('tests/remote/core_test.c','fuzz PASS')
    def test_actual_http_and_queue_lifecycle(self):self.compile_run('tests/remote/transport_test.c','disconnect PASS',True)
    def test_embedded_page_matches_current_source(self):
        component=ROOT/'firmware/components/player_remote'
        body=(component/'player_remote_page.h').read_text().split('{',1)[1].rsplit('}',1)[0]
        compressed=bytes(map(int,re.findall(r'\d+',body)))
        self.assertEqual(gzip.decompress(compressed),(component/'web/index.html').read_bytes())
if __name__=='__main__':unittest.main(verbosity=2)
