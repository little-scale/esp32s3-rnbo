# SPDX-License-Identifier: MIT
"""Fail-closed smoke-cache/profile and output protection; no devices/RNBO required."""
import copy
import importlib.util
import io
import re
import shutil
import subprocess
from contextlib import redirect_stdout,redirect_stderr
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("smoke_modules", ROOT / "tools/build_smoke_modules.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def manifest():
    return {"format": "rnbo-esp32s3-prepared-export", "format_version": 1,
            "rnbo_version": "1.4.4", "class_name": "rnbos3patch", "role": "fx",
            "sample_rate": 44100, "block_frames": 256, "audio_inputs": 2, "audio_outputs": 2,
            "parameter_count": 0, "voices": 1, "voice_topology": "single-export",
            "numerical_profile": "float32-strict", "scheduler_time": "float64",
            "defined_int32_wrap": True, "required_host_services": [], "midi_output_ports": 0,
            "midi_output_policy": "reject", "adaptations": smoke.ADAPTATIONS.copy(), "execution": "static-development",
            "editable_source_sha256": "a" * 64, "parameter_schema_sha256": "b" * 64, "source_tree_sha256": "c" * 64}


class SmokeModuleTests(unittest.TestCase):
    def test_signal_routing_reuses_only_the_strict_parameter_free_fx_profile(self):
        from build_hardware_smoke import routing_contract
        row={'surface':'patcher','role':'fx','syntax':'signal-object'}
        routing_contract(row,manifest())
        for field,value in (('parameter_count',1),('parameter_count',False),('audio_inputs',1),
                            ('audio_outputs',1),('midi_output_ports',1),('required_host_services',['dataref']),
                            ('numerical_profile','float32-auto-v1')):
            changed=manifest();changed[field]=value
            with self.subTest(field=field),self.assertRaises(smoke.ExportError):
                routing_contract(row,changed)

    def test_other_profiles_services_and_boolean_integer_fields_reject(self):
        smoke.validate_manifest(manifest())
        for field, value in (("role", "main"), ("block_frames", 128),
                             ("voices", True), ("numerical_profile", "float32-audio-v2"),
                             ("required_host_services", ["dataref"]), ("adaptations", [])):
            changed = manifest()
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(smoke.ExportError):
                smoke.validate_manifest(changed)
        changed = manifest()
        changed["optional_adapter"] = True
        with self.assertRaises(smoke.ExportError):
            smoke.validate_manifest(changed)

    def test_parameter_counts_are_typed_and_bounded_without_relaxing_profile(self):
        for count in range(33):
            changed=manifest();changed['parameter_count']=count
            smoke.validate_manifest(changed)
        for count in (True,False,-1,33,128,1.0,'1',None):
            changed=manifest();changed['parameter_count']=count
            with self.subTest(count=count),self.assertRaises(smoke.ExportError):
                smoke.validate_manifest(changed)
        for field,value in (('required_host_services',['dataref']),('voices',2),
                            ('midi_output_ports',1),('numerical_profile','float32-audio-v1')):
            changed=manifest();changed['parameter_count']=32;changed[field]=value
            with self.subTest(field=field),self.assertRaises(smoke.ExportError):
                smoke.validate_manifest(changed)

    def test_actual_worker_parameter_helpers_resolve_ids_order_events_and_fail_closed(self):
        source=(ROOT/'hardware-smoke/main/smoke.c').read_text()
        state=re.search(r'typedef struct \{\s*uint32_t resolved\[32\],next_event;.*?\} parameter_checks;',source,re.S).group()
        predicates=source[source.index('static bool word_finite'):source.index('static bool hex_digest')]
        helpers=source[source.index('static uint32_t float_word'):source.index('static uint64_t process_once')]
        prelude=r'''
#include <stdbool.h>
#include <stdint.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "rnbo_s3_module.h"
#include "smoke_types.h"
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"check at %d\n",__LINE__);exit(66); } } while(0)
enum {MANUAL_WARM_CALLS=4,TIMED_CALLS=16};
typedef struct {rnbo_s3_module module;void *context;} object_image;
static int mode;static uint32_t seen,indices[3];static float actuals[2];static int64_t timer;
static void allocation_probe_begin(void){}
static void allocation_probe_end(void){}
static unsigned allocation_probe_allocations(void){return 0;}
static unsigned allocation_probe_frees(void){return 0;}
static int64_t esp_timer_get_time(void){return ++timer;}
static uint32_t count(void *p){(void)p;return mode==9?0u:mode==7?3u:2u;}
static int info(void *p,uint32_t i,rnbo_s3_parameter_info *out){
    (void)p;*out=(rnbo_s3_parameter_info){.struct_bytes=sizeof *out,.index=i,
        .minimum=-8.f,.maximum=8.f,.initial=0.f,.exponent=1.f};
    strcpy(out->id,i?"drive":"beta");
    if(mode==2)out->maximum=4.f;
    if(mode==6)memset(out->id,'z',sizeof out->id);
    return RNBO_S3_OK;
}
static int value(void *p,uint32_t i,float *actual,float *normalized){
    (void)p;*actual=actuals[i];*normalized=(actuals[i]+8.f)/16.f;
    if(mode==3&&seen)*normalized=0.f;
    if(mode==5&&seen)*actual=0.f;
    return RNBO_S3_OK;
}
static int event(void *p,const rnbo_s3_event *e){
    (void)p;CHECK(e->struct_bytes==sizeof *e&&e->kind==RNBO_S3_PARAMETER_ACTUAL&&e->parameter_index<2u&&seen<3u);
    indices[seen++]=e->parameter_index;
    if(mode!=8||actuals[e->parameter_index]!=e->value)actuals[e->parameter_index]=e->value;
    return RNBO_S3_OK;
}
'''
        main=r'''
int main(int argc,char **argv){
    mode=argc>1?atoi(argv[1]):0;
    smoke_parameter_contract contracts[2]={{"drive",-8.f,8.f,0.f,1.f,0},{"beta",-8.f,8.f,0.f,1.f,0}};
    smoke_parameter_action actions[3]={{0,0,0x3f000000u},{0,1,0xbf000000u},{19,0,0xc1000000u}};
    smoke_case test={.id="boundary",.expected_parameter_count=2,.parameters=contracts,.parameter_event_count=3,.parameter_events=actions};
    if(mode==1)contracts[1].id="drive";
    if(mode==4)actions[0].before_call=19;
    if(mode==8){actions[0].value_word=0x80000000u;actions[1].value_word=0u;actions[1].parameter_slot=0u;}
    if(mode==9){test.expected_parameter_count=0;test.parameters=NULL;test.parameter_event_count=0;test.parameter_events=NULL;}
    object_image image={.module={.parameter_count=count,.parameter_info=info,.parameter_value=value,.event=event}};
    parameter_checks checks={0};verify_parameters(&image,&test,&checks);
    for(uint32_t call=0;call<20u;++call){
        apply_parameter_events(&image,&test,&checks,call);
        if(mode!=9&&call==0u)CHECK(seen==2u&&actuals[1]==(mode==8?0.f:.5f)&&actuals[0]==(mode==8?0.f:-.5f));
        if(mode!=9&&call>0u&&call<19u)CHECK(seen==2u);
    }
    if(mode==9){CHECK(!seen&&!checks.events&&!checks.total_us&&!checks.peak_us);return 0;}
    CHECK(seen==3u&&indices[0]==1u&&indices[1]==(mode==8?1u:0u)&&indices[2]==1u&&actuals[1]==-8.f);
    CHECK(checks.next_event==3u&&checks.events==3u&&checks.total_us==3u&&checks.peak_us==1u);
    CHECK(same_numeric_word(0x80000000u,0u)&&!same_numeric_word(0x3f000000u,0x3f000001u));
    return 0;
}
'''
        with tempfile.TemporaryDirectory()as temp:
            path=Path(temp);c=path/'parameters.c';c.write_text(prelude+state+predicates+helpers+main)
            compiler=shutil.which('cc');self.assertIsNotNone(compiler)
            subprocess.run([compiler,'-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-function',
                '-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(ROOT/'module-sdk/include'),
                '-I'+str(ROOT/'hardware-smoke/main'),str(c),'-o',str(path/'parameters')],check=True,capture_output=True,text=True)
            passed=subprocess.run([str(path/'parameters')],check=True,capture_output=True,text=True)
            records=passed.stdout.splitlines();self.assertEqual(len(records),3)
            self.assertIn('ordinal=0 before_call=0 parameter_slot=0 resolved_index=1',records[0])
            self.assertIn('ordinal=1 before_call=0 parameter_slot=1 resolved_index=0',records[1])
            self.assertIn('ordinal=2 before_call=19',records[2])
            self.assertTrue(all('event_us=1'in row for row in records))
            legacy=subprocess.run([str(path/'parameters'),'9'],check=True,capture_output=True,text=True)
            self.assertEqual(legacy.stdout,'')
            zeros=subprocess.run([str(path/'parameters'),'8'],check=True,capture_output=True,text=True)
            self.assertIn('value_word=80000000 actual_word=00000000',zeros.stdout)
            for mode in range(1,8):
                with self.subTest(mode=mode):
                    result=subprocess.run([str(path/'parameters'),str(mode)],capture_output=True,text=True)
                    self.assertEqual(result.returncode,66)

    def test_actual_output_comparator_prefers_shared_blocks_and_gates_strict_zero_lane(self):
        source=(ROOT/'hardware-smoke/main/smoke.c').read_text()
        state=re.search(r'typedef struct \{\s*uint64_t samples,.*?\} output_checks;',source,re.S).group()
        predicate=source[source.index('static bool word_finite'):source.index('static bool token')]
        comparator=source[source.index('static void compare_output'):source.index('static uint32_t float_word')]
        prelude=r'''
#include <stdbool.h>
#include <stdint.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "smoke_types.h"
#define RNBO_S3_BLOCK_FRAMES 256u
#define CHECK(x) do {if(!(x)){fprintf(stderr,"check %d\n",__LINE__);exit(66);}}while(0)
enum {MANUAL_WARM_CALLS=4,TIMED_CALLS=16};
static float storage[2][256];static float *const outputs[2]={storage[0],storage[1]};
static uint32_t right_capture[20u*256u];
'''
        main=r'''
static void fill(const uint32_t *words){
    for(unsigned i=0;i<256u;++i)for(unsigned ch=0;ch<2u;++ch)memcpy(&outputs[ch][i],&words[2u*i+ch],4u);
}
int main(void){
    uint32_t blocks[2][512],flat[20u*512u],zeros[512]={0};const uint32_t *refs[20];
    smoke_case test={.expected_blocks=flat,.expected_block_refs=refs};
    for(unsigned i=0;i<512u;++i){blocks[0][i]=0x3f800000u;blocks[1][i]=0x40000000u;test.expected[i]=0x40800000u;}
    for(unsigned i=0;i<20u*512u;++i)flat[i]=0x40400000u;
    for(unsigned call=0;call<20u;++call)refs[call]=blocks[call&1u];
    output_checks checks={.first_mismatch=UINT32_MAX,.first_mismatch_call=UINT32_MAX};
    for(unsigned call=0;call<20u;++call){fill(refs[call]);compare_output(&test,&checks);}
    CHECK(checks.samples==10240u&&!checks.bit_mismatches&&!checks.numeric_mismatches);
    for(unsigned call=0;call<20u;++call)for(unsigned frame=0;frame<256u;++frame)
        CHECK(right_capture[call*256u+frame]==refs[call][frame*2u+1u]);
    test.expected_block_refs=NULL;checks=(output_checks){.samples=2u*512u,.first_mismatch=UINT32_MAX};
    fill(flat+2u*512u);compare_output(&test,&checks);CHECK(!checks.bit_mismatches);
    test.expected_blocks=NULL;checks=(output_checks){.first_mismatch=UINT32_MAX};
    fill(test.expected);compare_output(&test,&checks);CHECK(!checks.bit_mismatches);
    for(unsigned call=0;call<20u;++call)refs[call]=zeros;
    test.expected_block_refs=refs;test.strict_zero_sign_channels=2u;test.absolute_tolerance=.001f;
    fill(zeros);uint32_t minus_zero=0x80000000u;
    memcpy(&outputs[0][0],&minus_zero,4u);memcpy(&outputs[1][0],&minus_zero,4u);
    checks=(output_checks){.samples=5u*512u,.first_mismatch=UINT32_MAX,.first_mismatch_call=UINT32_MAX};
    compare_output(&test,&checks);
    CHECK(checks.bit_mismatches==2u&&checks.zero_sign_differences==1u&&checks.strict_zero_sign_mismatches==1u);
    CHECK(checks.numeric_mismatches==1u&&!checks.within_tolerance_differences&&!checks.nonfinite_outputs&&checks.max_absolute_error==0.);
    CHECK(checks.first_mismatch_call==5u&&checks.first_mismatch==1u&&checks.first_actual==0x80000000u&&checks.first_expected==0u);
    CHECK(right_capture[5u*256u]==0x80000000u&&right_capture[5u*256u+1u]==0u);
    zeros[1]=minus_zero;fill(zeros);outputs[1][0]=0.f;
    checks=(output_checks){.first_mismatch=UINT32_MAX};compare_output(&test,&checks);
    CHECK(checks.numeric_mismatches==1u&&checks.strict_zero_sign_mismatches==1u&&!checks.zero_sign_differences);
    CHECK(checks.first_actual==0u&&checks.first_expected==minus_zero);
    zeros[1]=0u;fill(zeros);memcpy(&outputs[0][0],&minus_zero,4u);memcpy(&outputs[1][0],&minus_zero,4u);
    test.strict_zero_sign_channels=0u;checks=(output_checks){.first_mismatch=UINT32_MAX};compare_output(&test,&checks);
    CHECK(checks.zero_sign_differences==2u&&!checks.numeric_mismatches&&!checks.strict_zero_sign_mismatches&&!checks.within_tolerance_differences);
    test.strict_zero_sign_channels=3u;checks=(output_checks){.first_mismatch=UINT32_MAX};compare_output(&test,&checks);
    CHECK(checks.numeric_mismatches==2u&&checks.strict_zero_sign_mismatches==2u&&!checks.zero_sign_differences);
    return 0;
}
'''
        with tempfile.TemporaryDirectory()as temp:
            path=Path(temp);c=path/'compare.c';c.write_text(prelude+state+predicate+comparator+main)
            compiler=shutil.which('cc');self.assertIsNotNone(compiler)
            subprocess.run([compiler,'-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all',
                '-I'+str(ROOT/'hardware-smoke/main'),str(c),'-o',str(path/'compare')],check=True,capture_output=True,text=True)
            subprocess.run([str(path/'compare')],check=True,capture_output=True,text=True)

    def test_actual_host_arena_gate_preserves_default_and_scopes_two_mib_override(self):
        compiler=shutil.which('clang')or shutil.which('cc')
        if not compiler:self.skipTest('A C compiler is needed for the actual admission helper')
        source=(ROOT/'object-benchmark/main/module_host.c').read_text()
        default=source[source.index('#ifndef RNBO_TEST_MAX_ARENA_BYTES'):source.index('_Static_assert(RNBO_TEST_MAX_ARENA_BYTES')]
        helper=re.search(r'static bool caller_arena_allowed\(uint32_t bytes\).*?^}',source,re.S|re.M).group()
        shared='assert(!caller_arena_allowed(0));assert(!caller_arena_allowed(4095));assert(caller_arena_allowed(4096));assert(caller_arena_allowed(1048576));assert(!caller_arena_allowed(UINT32_MAX));'
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp)
            for large in (False,True):
                checks=('assert(caller_arena_allowed(1048577));assert(caller_arena_allowed(2097152));assert(!caller_arena_allowed(2097153));'
                        if large else'assert(!caller_arena_allowed(1048577));assert(!caller_arena_allowed(2097152));')
                path=root/('large.c'if large else'default.c');binary=path.with_suffix('')
                path.write_text('#include <stdbool.h>\n#include <stdint.h>\n#include <assert.h>\n'+default+helper+'\nint main(void){'+shared+checks+'return 0;}\n')
                command=[compiler,'-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=undefined']
                if large:command.append('-DRNBO_TEST_MAX_ARENA_BYTES=2097152u')
                subprocess.run([*command,str(path),'-o',str(binary)],check=True,capture_output=True)
                subprocess.run([str(binary)],check=True,capture_output=True)
        self.assertIn('CHECK(caller_arena_allowed(arena_bytes));',source)
        cmake=(ROOT/'hardware-smoke/main/CMakeLists.txt').read_text()
        self.assertIn('RNBO_TEST_MAX_ARENA_BYTES=2097152u',cmake)

    def test_wrapper_changes_only_exact_export_paths_and_output(self):
        command = ["compiler", "-I/old", "-I/old/common", "-DNAME=/old", "-o", "old.o", "-c", "wrapper.cpp"]
        result = smoke.rewrite_wrapper(command, Path("/old"), Path("/new"), Path("/new.o"))
        self.assertEqual(result, ["compiler", "-I/new", "-I/new/common", "-DNAME=/old", "-o", "/new.o", "-c", "wrapper.cpp"])
        self.assertEqual(command[1], "-I/old")
        with self.assertRaises(smoke.ExportError):
            smoke.rewrite_wrapper(command + ["-I/old"], Path("/old"), Path("/new"), Path("/new.o"))

    def test_arena_tier_rewrites_only_one_wrapper_macro_and_never_the_input(self):
        command=['compiler','-O2','-DRNBO_S3_DYNAMIC_MAX_ARENA_BYTES=4096u','-DOTHER=4096u','-c','wrapper.cpp']
        original=command.copy()
        self.assertEqual(smoke.rewrite_arena_limit(command,4096),command)
        for limit in (1048576,2097152):
            changed=smoke.rewrite_arena_limit(command,limit)
            self.assertEqual(changed,[*command[:2],f'-DRNBO_S3_DYNAMIC_MAX_ARENA_BYTES={limit}u',*command[3:]])
        self.assertEqual(command,original)
        for bad in (True,0,8192,4194304,'1048576'):
            with self.subTest(value=bad),self.assertRaises(smoke.ExportError):smoke.rewrite_arena_limit(command,bad)
        for bad_command in (command[:2]+command[3:],command+['-DRNBO_S3_DYNAMIC_MAX_ARENA_BYTES=4096u'],
                            [v.replace('=4096u','=1048576u')for v in command]):
            with self.assertRaises(smoke.ExportError):smoke.rewrite_arena_limit(bad_command,1048576)

    def test_cli_exposes_only_the_three_reviewed_tiers(self):
        args=['tool','--prepared-root','/prepared','--base-build','/cache','--out','/new']
        for choice in (None,4096,1048576,2097152):
            argv=args+([]if choice is None else['--max-arena-bytes',str(choice)])
            with mock.patch('sys.argv',argv),mock.patch.object(smoke,'build_batch',return_value={'result':'passed','built':1,'failed':0})as build,redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit)as exit:smoke.main()
                self.assertEqual(exit.exception.code,0);self.assertEqual(build.call_args.args[-1],4096 if choice is None else choice)
        with mock.patch('sys.argv',args+['--max-arena-bytes','8192']),redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit)as exit:smoke.main()
            self.assertEqual(exit.exception.code,2)

    def test_large_candidate_batch_keeps_original_4k_control_and_support_cache(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);prepared=root/'prepared';prepared.mkdir();(prepared/'candidate').mkdir()
            base=root/'cache';base.mkdir();(base/'build-report.json').write_bytes(b'cached report')
            artifact=base/'original.elf';artifact.write_bytes(b'unchanged control image')
            snapshot={'prepared_files_sha256':{'rnbo_source.h':'a'*64}}
            cache={'report':{'artifact':{'path':str(artifact)}},'source_files_sha256':{},'binding':{},
                'compiler':Path('/compiler'),'compiler_version':'same','archives':{},'old_export':root/'original-export',
                'old_prepared_snapshot':snapshot,'dependency_files':{},'dependencies_dir':root/'dependencies'}
            outputs=[{'id':'cache-control','status':'built','artifact':{'path':str(artifact)}},
                     {'id':'candidate','status':'built','artifact':{'path':'unused'}}]
            with mock.patch.object(smoke,'verify_prepared',return_value=({},manifest(),snapshot)),                 mock.patch.object(smoke,'inspect_cache',return_value=cache),                 mock.patch.object(smoke,'sources',return_value={}),                 mock.patch.object(smoke,'build_one',side_effect=outputs)as build,redirect_stdout(io.StringIO()):
                result=smoke.build_batch(prepared,base,root/'out',2097152)
            self.assertTrue(result['cache_control_whole_ELF_equal'])
            self.assertEqual(result['max_arena_bytes'],2097152);self.assertEqual(result['cache_control_max_arena_bytes'],4096)
            self.assertEqual([call.args[-1]for call in build.call_args_list],[4096,2097152])
            self.assertTrue(all(call.args[3]is cache for call in build.call_args_list))
            self.assertEqual(artifact.read_bytes(),b'unchanged control image')

    def test_unknown_link_or_strip_flag_cannot_enter_replay(self):
        gcc, strip = Path("/tool/gcc"), Path("/tool/strip")
        archives = {"libm": {"path": "/tool/libm.a"}, "libgcc": {"path": "/tool/libgcc.a"}}
        link = [str(gcc), *smoke.LINK_FLAGS, "esp-idf/main/libmain.a", "-Wl,-Bsymbolic", "-Wl,--exclude-libs,ALL",
                "-Wl,--start-group", "/tool/libm.a", "/tool/libgcc.a", "-Wl,--end-group", "-o", "rnbo_s3_dynamic.app.elf"]
        stripping = [str(strip), *smoke.STRIP_FLAGS, "rnbo_s3_dynamic.app.elf"]
        text = "  COMMAND = cd /cache && " + " ".join(link) + " && cmake copy a b && " + " ".join(stripping)
        self.assertEqual(smoke.link_recipe(text, gcc, strip, archives), (link, stripping))
        for changed in (text.replace("/tool/libm.a", "/other/libm.a"), text.replace("-fPIC", "-ffast-math"),
                        text.replace("--strip-unneeded", "--strip-all")):
            with self.assertRaises(smoke.ExportError):
                smoke.link_recipe(changed, gcc, strip, archives)

    def test_reused_file_tamper_rejects(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "cache.a"
            path.write_bytes(b"original")
            records = {str(path): smoke.sha(path)}
            smoke.assert_hashes(records)
            path.write_bytes(b"tampered")
            with self.assertRaises(smoke.ExportError):
                smoke.assert_hashes(records)

    def test_existing_output_and_linked_input_are_rejected_before_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            out = root / "old"
            out.mkdir()
            sentinel = out / "keep"
            sentinel.write_bytes(b"unchanged")
            with self.assertRaises(smoke.ExportError):
                smoke.build_batch(root / "missing", root / "cache", out)
            self.assertEqual(sentinel.read_bytes(), b"unchanged")
            prepared = root / "prepared"
            prepared.mkdir()
            (prepared / "linked").symlink_to(out, target_is_directory=True)
            fresh = root / "new"
            with self.assertRaises(smoke.ExportError):
                smoke.build_batch(prepared, root / "cache", fresh)
            self.assertFalse(fresh.exists())


if __name__ == "__main__":
    unittest.main()
