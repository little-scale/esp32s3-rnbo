# SPDX-License-Identifier: MIT
"""Exercise the actual C admission/conditioning code with real cJSON, no GPIO."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host/compiler'))
from physical_inputs import extract

SOURCE = r'''
#include "player_inputs.h"
#include "cJSON.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static const char *id_at(void *unused,unsigned i) {
    (void)unused;
    /* Deliberately reorder module indices relative to the metadata. */
    static const char *ids[]={"touch-id","gate-id","pitch-id"};return ids[i];
}
int main(int argc,char **argv) {
    assert(argc==2);char raw[8192]={0};FILE *f=fopen(argv[1],"r");assert(f);
    size_t bytes=fread(raw,1,sizeof raw-1,f);assert(bytes>0);fclose(f);
    cJSON *metadata=cJSON_Parse(raw);assert(metadata);player_input_plan plan;char error[192];
    assert(player_inputs_plan_parse(metadata,true,7,8,9,3,id_at,0,&plan,error,sizeof error));
    assert(plan.count==3&&plan.bindings[0].gpio==1&&plan.bindings[0].parameter_index==2);
    assert(plan.bindings[1].gpio==43&&plan.bindings[1].parameter_index==1);
    assert(plan.bindings[2].gpio==4&&plan.bindings[2].parameter_index==0);
    player_input_plan rejected;
    assert(!player_inputs_plan_parse(metadata,false,-1,-1,-1,3,id_at,0,&rejected,error,sizeof error));
    assert(!player_inputs_plan_parse(metadata,true,1,8,9,3,id_at,0,&rejected,error,sizeof error));
    assert(!player_inputs_plan_parse(metadata,true,7,8,9,2,id_at,0,&rejected,error,sizeof error));
    cJSON *rows=cJSON_GetObjectItemCaseSensitive(cJSON_GetObjectItemCaseSensitive(metadata,"physical_inputs"),"bindings");
    cJSON *analog=cJSON_GetArrayItem(rows,0),*digital=cJSON_GetArrayItem(rows,1);
    cJSON_ReplaceItemInObjectCaseSensitive(digital,"pin",cJSON_CreateString("GPIO1"));
    assert(!player_inputs_plan_parse(metadata,true,7,8,9,3,id_at,0,&rejected,error,sizeof error));
    cJSON_ReplaceItemInObjectCaseSensitive(digital,"pin",cJSON_CreateString("D6"));
    cJSON_AddNumberToObject(analog,"typo",1);
    assert(!player_inputs_plan_parse(metadata,true,7,8,9,3,id_at,0,&rejected,error,sizeof error));
    cJSON_DeleteItemFromObjectCaseSensitive(analog,"typo");
    cJSON_AddNumberToObject(analog,"raw_min",0); /* Duplicate keys cannot override. */
    assert(!player_inputs_plan_parse(metadata,true,7,8,9,3,id_at,0,&rejected,error,sizeof error));
    cJSON_Delete(metadata);
    cJSON *empty=cJSON_Parse("{}");
    assert(player_inputs_plan_parse(empty,false,-1,-1,-1,3,id_at,0,&rejected,error,sizeof error)&&!rejected.count);cJSON_Delete(empty);

    player_input_binding b=plan.bindings[0];player_input_state s={0};float v=-1;
    b.smooth_ms=0;b.raw_min=100;b.raw_max=1100;
    assert(player_input_sample(&b,&s,0,0,&v)&&v==0);
    assert(!player_input_sample(&b,&s,50,4000,&v));
    assert(player_input_sample(&b,&s,600,8000,&v)&&v==.5f);
    assert(!player_input_sample(&b,&s,601,12000,&v)); /* Jitter suppression. */
    assert(player_input_sample(&b,&s,4095,16000,&v)&&v==1);
    assert(!player_input_sample(&b,&s,4095,20000,&v)); /* Idle control never reasserts. */
    memset(&s,0,sizeof s);b.invert=true;
    assert(player_input_sample(&b,&s,100,0,&v)&&v==1);
    assert(player_input_sample(&b,&s,1100,4000,&v)&&v==0);
    memset(&s,0,sizeof s);b.invert=false;b.smooth_ms=10;b.deadband=0;
    assert(player_input_sample(&b,&s,100,0,&v)&&v==0);
    assert(player_input_sample(&b,&s,1100,10000,&v)&&v==.5f);
    for(int64_t t=20000;t<1000000;t+=10000)(void)player_input_sample(&b,&s,1100,t,&v);
    assert(v==1); /* Exact settled endpoint despite smoothing. */

    b=plan.bindings[1];memset(&s,0,sizeof s);
    assert(!player_input_sample(&b,&s,1,0,&v));
    assert(player_input_sample(&b,&s,1,8000,&v)&&v==0); /* Pull-up button released. */
    assert(!player_input_sample(&b,&s,0,12000,&v));
    assert(!player_input_sample(&b,&s,1,16000,&v));
    assert(!player_input_sample(&b,&s,0,20000,&v));
    assert(!player_input_sample(&b,&s,0,24000,&v));
    assert(player_input_sample(&b,&s,0,28000,&v)&&v==1);
    assert(!player_input_sample(&b,&s,0,32000,&v));
    b=plan.bindings[2];b.debounce_ms=0;memset(&s,0,sizeof s);
    assert(!player_input_sample(&b,&s,0,0,&v)&&!s.calibration_samples);
    for(unsigned i=0;i<63;++i)assert(!player_input_sample(&b,&s,1000,(int64_t)i*4000,&v));
    assert(player_input_sample(&b,&s,1000,252000,&v)&&v==0);
    assert(s.baseline==1000);
    assert(player_input_sample(&b,&s,1100,256000,&v)&&v==1);
    for(unsigned i=0;i<2000;++i)assert(!player_input_sample(&b,&s,1100,260000+(int64_t)i*4000,&v));
    assert(s.baseline==1000); /* A held touch cannot recalibrate itself away. */
    assert(!player_input_sample(&b,&s,1070,9000000,&v)); /* Hysteresis holds. */
    assert(player_input_sample(&b,&s,1050,9004000,&v)&&v==0);
    puts("physical input admission, analog range/smoothing/jitter, button debounce and touch state passed");
}
'''


class PlayerInputsTests(unittest.TestCase):
    def test_actual_c_parser_and_control_state(self):
        cc = shutil.which('cc')
        cjson = Path(os.environ.get('IDF_PATH', str(Path.home() / 'esp/esp-idf'))) / 'components/json/cJSON'
        if not cc or not (cjson / 'cJSON.c').is_file():
            self.skipTest('Native compiler and installed ESP-IDF cJSON required')
        component = ROOT / 'firmware/components/player_inputs'
        plan = extract([dict(paramId=identity, meta={'esp32': dict(type=kind, pin=pin)})
                        for identity, kind, pin in [('pitch-id','analog','A0'),('gate-id','digital','D6'),('touch-id','touch','D3')]])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.c').write_text(SOURCE);(p/'plan.json').write_text(json.dumps({'physical_inputs':plan}))
            command=[cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off',
                     '-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(component/'include'),'-I'+str(cjson),
                     str(p/'test.c'),str(component/'player_inputs_core.c'),str(cjson/'cJSON.c'),'-lm','-o',str(p/'test')]
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(p/'test'),str(p/'plan.json')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
