# SPDX-License-Identifier: MIT
"""Public CLI safety/admission tests; the licensed end-to-end run is separate."""
import json
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import qualify_wave3 as q

class PublicDriverTests(unittest.TestCase):
    def test_reviewed_catalogue_is_fixed_and_near_match_is_rejected(self):
        catalog=q.load_catalog()
        self.assertEqual(len(catalog['fixtures']),10)
        self.assertEqual(sum(len(f['cases'])for f in catalog['fixtures']),45)
        changed=json.loads(q.CATALOG.read_text());changed['fixtures'][0]['independent_absolute_error_limit']=3e-5
        with self.assertRaisesRegex(q.QualificationError,'catalogue changed'):
            q.load_catalog(json.dumps(changed).encode())

    def test_onepole_selection_is_explicit_isolated_and_retains_the_original_catalogue(self):
        original=q.load_catalog();before=copy.deepcopy(original)
        selected=q.select_catalog(original,onepole_only=True)
        self.assertEqual(len(selected['fixtures']),3)
        self.assertEqual(sum(len(f['cases'])for f in selected['fixtures']),15)
        self.assertEqual({f['object_spelling']for f in selected['fixtures']},{'onepole~'})
        selected['fixtures'][0]['cases'].clear()
        self.assertEqual(original,before)
        self.assertEqual(q.select_catalog(original),before)
        self.assertEqual(sum(len(f['cases'])for f in original['fixtures']),45)

    def test_profile_and_selection_require_real_booleans_before_tools_or_output(self):
        for keyword in ('stable_onepole','onepole_only'):
            for value in (0,1,None,'true',[]):
                with tempfile.TemporaryDirectory()as name:
                    out=Path(name)/'new-run'
                    with self.subTest(keyword=keyword,value=value),self.assertRaisesRegex(q.QualificationError,'booleans'):
                        q.qualify(out,**{keyword:value})
                    self.assertFalse(out.exists())

    def test_help_exposes_the_separate_profile_and_selection(self):
        ran=subprocess.run([sys.executable,str(Path(q.__file__)),'--help'],capture_output=True,text=True)
        self.assertEqual(ran.returncode,0)
        self.assertIn('--onepole-only',ran.stdout)
        self.assertIn('--stable-onepole',ran.stdout)
        self.assertIn('other objects stay strict',ran.stdout)

    def test_existing_output_is_rejected_without_overwriting_data(self):
        build=q.ROOT/'build';build.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build)as name:
            root=Path(name);sentinel=root/'sentinel.txt';sentinel.write_text('keep this')
            ran=subprocess.run([sys.executable,str(Path(q.__file__)),'--out',str(root)],capture_output=True,text=True)
            self.assertEqual(ran.returncode,2)
            self.assertIn('Output already exists',ran.stderr)
            self.assertEqual(sentinel.read_text(),'keep this')
            self.assertEqual(sorted(p.name for p in root.iterdir()),['sentinel.txt'])

    def test_output_outside_ignored_build_is_rejected_before_any_tool_runs(self):
        with tempfile.TemporaryDirectory()as name:
            out=Path(name)/'new-run'
            ran=subprocess.run([sys.executable,str(Path(q.__file__)),'--out',str(out)],capture_output=True,text=True)
            self.assertEqual(ran.returncode,2)
            self.assertIn('below this repository',ran.stderr)
            self.assertFalse(out.exists())

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=q.ROOT/'build')as name,tempfile.TemporaryDirectory()as outside:
            root=Path(name);(root/'alias').symlink_to(outside,target_is_directory=True)
            with self.assertRaises(q.QualificationError):q.validate_output(root/'alias'/'new-run')
            self.assertFalse((Path(outside)/'new-run').exists())

    def test_help_is_available_without_export_or_compilation(self):
        ran=subprocess.run([sys.executable,str(Path(q.__file__)),'--help'],capture_output=True,text=True)
        self.assertEqual(ran.returncode,0)
        self.assertIn('--out',ran.stdout)
        self.assertIn('--rnbo-dir',ran.stdout)
        self.assertIn('No hardware is accessed',ran.stdout)

    def test_readback_audit_rejects_reordered_same_vector_commands(self):
        plan,trace=self.readback_program()
        self.assertEqual(q.audit_readbacks(trace,plan)['event_readback_records'],2)
        trace[0],trace[1]=trace[1],trace[0]
        with self.assertRaisesRegex(q.QualificationError,'source order'):
            q.audit_readbacks(trace,plan)

    def test_readback_audit_rejects_silent_setter_or_clock_advance(self):
        plan,trace=self.readback_program()
        wrong=copy.deepcopy(trace);wrong[1]['actual_bits']=['3f000000']
        with self.assertRaisesRegex(q.QualificationError,'actual readback'):
            q.audit_readbacks(wrong,plan)
        wrong=copy.deepcopy(trace);wrong[0]['position']=256
        with self.assertRaisesRegex(q.QualificationError,'advanced the sample clock'):
            q.audit_readbacks(wrong,plan)

    def test_incomplete_or_truncated_oracle_results_never_count_as_accuracy_pass(self):
        catalog={'fixtures':[{'id':'fixture','cases':[{'id':'case','lifecycles':2}]}]}
        with tempfile.TemporaryDirectory()as name:
            root=Path(name);(root/'output').write_bytes(b'\0'*16)
            record={'returncode':0,'completed':False,'statistics':{'cycles':[{'cycle':i,'captured_blocks':0}for i in range(2)]},'files':{s:{'path':'output','sha256':'test'}for s in('.f32','.pcm16')},'independent_accuracy':[]}
            for completed,left_count,right_count in((False,0,0),(True,0,0),(True,1,1),(True,2,1)):
                with self.subTest(completed=completed,left_count=left_count,right_count=right_count):
                    a=copy.deepcopy(record);b=copy.deepcopy(record);a['completed']=b['completed']=completed
                    a['independent_accuracy']=[{'passed':True}]*left_count;b['independent_accuracy']=[{'passed':True}]*right_count
                    rows,_=q.compare_results(catalog,{'fixture--O3':{'cases':{'case':a}},'fixture--UBSan':{'cases':{'case':b}}},root)
                    self.assertFalse(rows[0]['accuracy_evaluated'])
                    self.assertFalse(rows[0]['accuracy_pass'])

    @staticmethod
    def readback_program():
        events=[{'block':0,'id':'value','index':0,'value_bits':bits}for bits in('3f000000','3f800000')]
        plan={'parameter_schema':[{'initialValue':0}],'lifecycles':1,'blocks':1,'events':events}
        trace=[{'kind':'event','cycle':0,'block':0,'order':i,'id':'value','index':0,'requested_bits':e['value_bits'],'actual_bits':[e['value_bits']],'normalized_bits':[e['value_bits']],'result':0,'position':0,'blocks':0}for i,e in enumerate(events)]
        trace.append({'kind':'block','cycle':0,'block':0,'result':0,'actual_bits':['3f800000'],'normalized_bits':['3f800000'],'position':256,'blocks':1})
        return plan,trace

if __name__=='__main__':unittest.main()
