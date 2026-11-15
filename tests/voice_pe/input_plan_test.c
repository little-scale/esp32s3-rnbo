// SPDX-License-Identifier: MIT
#include "player_inputs.h"
#include "cJSON.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
static const char *id_at(void *unused,unsigned index){(void)unused;const char *ids[]={"freq","level","mute"};return ids[index];}
static bool parse(const char *text,bool enabled,player_voice_plan *plan){
    char error[128];cJSON *json=cJSON_Parse(text);assert(json);
    bool result=player_voice_plan_parse(json,enabled,3,id_at,NULL,plan,error,sizeof error);
    cJSON_Delete(json);return result;
}
int main(void){
    player_voice_plan p;
    assert(parse("{}",false,&p)&&p.count==0&&p.index[0]==UINT32_MAX);
    const char *valid="{\"voice_pe_inputs\":{\"version\":1,\"board\":\"voice-pe\",\"bindings\":[{\"parameter_id\":\"freq\",\"input\":\"dial\"},{\"parameter_id\":\"level\",\"input\":\"button\"},{\"parameter_id\":\"mute\",\"input\":\"microphone_mute\"}]}}";
    assert(parse(valid,true,&p)&&p.count==3&&p.index[0]==0&&p.index[1]==1&&p.index[2]==2);
    assert(!parse(valid,false,&p));
    const char *bad[]={
      "{\"voice_pe_inputs\":{\"version\":true,\"board\":\"voice-pe\",\"bindings\":[]}}",
      "{\"voice_pe_inputs\":{\"version\":1,\"board\":\"xiao\",\"bindings\":[{\"parameter_id\":\"freq\",\"input\":\"dial\"}]}}",
      "{\"voice_pe_inputs\":{\"version\":1,\"board\":\"voice-pe\",\"bindings\":[{\"parameter_id\":\"unknown\",\"input\":\"dial\"}]}}",
      "{\"voice_pe_inputs\":{\"version\":1,\"board\":\"voice-pe\",\"bindings\":[{\"parameter_id\":\"freq\",\"input\":\"GPIO16\"}]}}",
      "{\"voice_pe_inputs\":{\"version\":1,\"board\":\"voice-pe\",\"bindings\":[{\"parameter_id\":\"freq\",\"input\":\"dial\"},{\"parameter_id\":\"freq\",\"input\":\"button\"}]}}"
    };
    for(unsigned i=0;i<sizeof bad/sizeof *bad;++i)assert(!parse(bad[i],true,&p));
    puts("PASS: Voice PE source/schema/board/ID admission and normalized parameter routing plan");
}
