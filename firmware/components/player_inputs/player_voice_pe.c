// SPDX-License-Identifier: MIT
#include "player_inputs.h"
#include "cJSON.h"
#include <stdio.h>
#include <string.h>
#include <stdint.h>
static bool fail(char *out,size_t size){if(out&&size)snprintf(out,size,"Invalid/unsupported Voice PE semantic input plan");return false;}
bool player_voice_plan_parse(const cJSON *metadata,bool enabled,unsigned count,
                            const char *(*id_at)(void *,unsigned),void *ctx,
                            player_voice_plan *plan,char *error,size_t size)
{
    *plan=(player_voice_plan){.index={UINT32_MAX,UINT32_MAX,UINT32_MAX}};
    const cJSON *p=cJSON_GetObjectItemCaseSensitive(metadata,"voice_pe_inputs");
    if(!p)return true;
    if(!enabled || !cJSON_IsObject(p) || cJSON_GetArraySize(p)!=3)return fail(error,size);
    const cJSON *v=cJSON_GetObjectItemCaseSensitive(p,"version"),*b=cJSON_GetObjectItemCaseSensitive(p,"board"),
        *rows=cJSON_GetObjectItemCaseSensitive(p,"bindings");
    if(!cJSON_IsNumber(v)||v->valuedouble!=1 || !cJSON_IsString(b)||strcmp(b->valuestring,"voice-pe") ||
       !cJSON_IsArray(rows)||cJSON_GetArraySize(rows)<1||cJSON_GetArraySize(rows)>3)return fail(error,size);
    const char *names[]={"dial","button","microphone_mute"};
    for(const cJSON *row=rows->child;row;row=row->next){
        const cJSON *id=cJSON_GetObjectItemCaseSensitive(row,"parameter_id"),*input=cJSON_GetObjectItemCaseSensitive(row,"input");
        if(!cJSON_IsObject(row)||cJSON_GetArraySize(row)!=2 || !cJSON_IsString(id)||!cJSON_IsString(input))return fail(error,size);
        unsigned source=3,index=count;
        for(unsigned i=0;i<3;++i)if(!strcmp(input->valuestring,names[i]))source=i;
        for(unsigned i=0;i<count;++i)if(!strcmp(id->valuestring,id_at(ctx,i)))index=i;
        if(source==3||index==count||plan->index[source]!=UINT32_MAX)return fail(error,size);
        for(unsigned i=0;i<3;++i)if(plan->index[i]==index)return fail(error,size);
        plan->index[source]=index;++plan->count;
    }
    return true;
}
