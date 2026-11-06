# SPDX-License-Identifier: MIT
"""Actual C metadata and patch-area gesture tests; no display or board IO."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host/compiler'))
from touchscreen_inputs import extract
SOURCE=r'''
#include "player_inputs.h"
#include "cJSON.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static unsigned calls,indices[128];static float values[128];static bool accept=true;
static bool publish(unsigned i,float n){assert(calls<128);indices[calls]=i;values[calls++]=n;return accept;}
static const char *id(void *c,unsigned i){(void)c;static const char *ids[]={"gate","level","pitch"};return ids[i];}
int main(int argc,char **argv){
 assert(argc==2);char raw[4096]={0},error[192];FILE *f=fopen(argv[1],"r");assert(f);assert(fread(raw,1,sizeof raw-1,f)>0);fclose(f);
 cJSON *meta=cJSON_Parse(raw);assert(meta);player_screen_plan p,rejected;
 assert(player_screen_plan_parse(meta,true,3,id,NULL,&p,error,sizeof error));assert(p.count==3);
 assert(p.bindings[0].parameter_index==0&&p.bindings[1].parameter_index==2&&p.bindings[2].parameter_index==1);
 assert(!player_screen_plan_parse(meta,false,3,id,NULL,&rejected,error,sizeof error));
 assert(!player_screen_plan_parse(meta,true,2,id,NULL,&rejected,error,sizeof error));
 cJSON *o=cJSON_GetObjectItemCaseSensitive(meta,"touchscreen_inputs"),*rows=cJSON_GetObjectItemCaseSensitive(o,"bindings"),*first=cJSON_GetArrayItem(rows,0);
 cJSON_ReplaceItemInObjectCaseSensitive(o,"area",cJSON_CreateString("screen"));assert(!player_screen_plan_parse(meta,true,3,id,NULL,&rejected,error,sizeof error));
 cJSON_ReplaceItemInObjectCaseSensitive(o,"area",cJSON_CreateString("patch"));
 cJSON_AddNumberToObject(first,"extra",1);assert(!player_screen_plan_parse(meta,true,3,id,NULL,&rejected,error,sizeof error));cJSON_DeleteItemFromObjectCaseSensitive(first,"extra");
 cJSON_AddStringToObject(first,"axis","x");assert(!player_screen_plan_parse(meta,true,3,id,NULL,&rejected,error,sizeof error));cJSON_Delete(meta);
 meta=cJSON_Parse("{}");assert(player_screen_plan_parse(meta,false,0,id,NULL,&rejected,error,sizeof error)&&!rejected.count);cJSON_Delete(meta);
 player_screen_state s={0};assert(player_screen_publish(&p,&s,publish));assert(calls==1&&indices[0]==0&&values[0]==0);calls=0;
 player_screen_contact(&s,PLAYER_SCREEN_BEGIN,-1,20,336,232);player_screen_contact(&s,PLAYER_SCREEN_MOVE,100,20,336,232);
 assert(!s.down&&!s.captured);assert(player_screen_publish(&p,&s,publish)&&!calls); /* Starts outside stay outside. */
 player_screen_contact(&s,PLAYER_SCREEN_BEGIN,0,0,336,232);assert(s.down);assert(player_screen_publish(&p,&s,publish));
 assert(calls==3&&indices[0]==2&&values[0]==0&&indices[1]==1&&values[1]==0&&indices[2]==0&&values[2]==1);calls=0;
 assert(player_screen_publish(&p,&s,publish)&&!calls); /* No repeated events for a stationary finger. */
 player_screen_contact(&s,PLAYER_SCREEN_MOVE,335,231,336,232);assert(player_screen_publish(&p,&s,publish));
 assert(calls==2&&values[0]==1&&values[1]==1);calls=0;
 player_screen_contact(&s,PLAYER_SCREEN_MOVE,336,231,336,232);assert(!s.down);assert(player_screen_publish(&p,&s,publish));
 assert(calls==1&&indices[0]==0&&values[0]==0&&s.x==1&&s.y==1);calls=0;
 player_screen_contact(&s,PLAYER_SCREEN_MOVE,100,100,336,232);assert(!s.down);assert(player_screen_publish(&p,&s,publish)&&!calls);
 player_screen_contact(&s,PLAYER_SCREEN_BEGIN,100,100,336,232);assert(player_screen_publish(&p,&s,publish)&&calls==3);calls=0;
 player_screen_contact(&s,PLAYER_SCREEN_END,0,0,336,232);accept=false;
 assert(!player_screen_publish(&p,&s,publish)&&calls==1);calls=0;accept=true;
 assert(player_screen_publish(&p,&s,publish)&&calls==1&&values[0]==0);calls=0; /* Failed releases retry. */
 player_screen_reset_gates(&p,&s);assert(player_screen_publish(&p,&s,publish)&&calls==1);calls=0;
 p.bindings[1].invert=true;p.bindings[0].invert=true;
 player_screen_contact(&s,PLAYER_SCREEN_BEGIN,335,231,336,232);assert(player_screen_publish(&p,&s,publish));
 assert(calls==3&&values[0]==0&&values[2]==0);calls=0;
 player_screen_cancel(&s);assert(player_screen_publish(&p,&s,publish)&&calls==1&&values[0]==1);
 puts("AMOLED patch-area metadata, bounds, XY-before-gate, hold/release and retry passed");
}
'''
class TouchscreenCTest(unittest.TestCase):
 def test_actual_parser_and_gesture_core(self):
  cc=shutil.which('cc');cj=Path(os.environ.get('IDF_PATH',str(Path.home()/'esp/esp-idf')))/'components/json/cJSON'
  if not cc or not (cj/'cJSON.c').is_file():self.skipTest('Native compiler and cJSON required')
  component=ROOT/'firmware/components/player_inputs'
  plan=extract([dict(paramId=i,meta={'esp32':dict(type='touchscreen',axis=a)}) for i,a in [('gate','pressed'),('pitch','x'),('level','y')]])
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'test.c').write_text(SOURCE);(p/'plan.json').write_text(json.dumps({'touchscreen_inputs':plan}))
   command=[cc,'-std=c11','-Wall','-Wextra','-Werror','-O2','-fno-fast-math','-ffp-contract=off','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(component/'include'),'-I'+str(cj),str(p/'test.c'),str(component/'player_touchscreen.c'),str(cj/'cJSON.c'),'-lm','-o',str(p/'test')]
   r=subprocess.run(command,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   r=subprocess.run([str(p/'test'),str(p/'plan.json')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
