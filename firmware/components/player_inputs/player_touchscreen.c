// SPDX-License-Identifier: MIT
#include "player_inputs.h"
#include "cJSON.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
static bool fail(char *error,size_t n,const char *message)
{if(error&&n)snprintf(error,n,"%s",message);return false;}
static bool fields(const cJSON *o,const char *const *names,unsigned n)
{
    if(!cJSON_IsObject(o))return false;
    for(const cJSON *p=o->child;p;p=p->next){
        bool known=false;for(unsigned i=0;i<n;++i)if(!strcmp(p->string,names[i]))known=true;
        if(!known)return false;
        for(const cJSON *q=p->next;q;q=q->next)if(!strcmp(p->string,q->string))return false;
    }return true;
}
bool player_screen_plan_parse(const cJSON *metadata,bool amoled,unsigned count,
                              const char *(*id_at)(void *,unsigned),void *context,
                              player_screen_plan *plan,char *error,size_t capacity)
{
    memset(plan,0,sizeof *plan);const cJSON *o=NULL;
    for(const cJSON *p=metadata?metadata->child:NULL;p;p=p->next)if(!strcmp(p->string,"touchscreen_inputs")){
        if(o)return fail(error,capacity,"Duplicate touchscreen_inputs metadata");
        o=p;
    }
    if(!o)return true;
    if(!amoled)return fail(error,capacity,"Touchscreen bindings require the AMOLED board");
    static const char *const names[]={"version","board","area","bindings"};
    const cJSON *v=cJSON_GetObjectItemCaseSensitive(o,"version"),*b=cJSON_GetObjectItemCaseSensitive(o,"board"),
                *area=cJSON_GetObjectItemCaseSensitive(o,"area"),*rows=cJSON_GetObjectItemCaseSensitive(o,"bindings");
    if(!fields(o,names,4)||!cJSON_IsNumber(v)||v->valuedouble!=1||!cJSON_IsString(b)||strcmp(b->valuestring,"amoled")||
       !cJSON_IsString(area)||strcmp(area->valuestring,"patch")||!cJSON_IsArray(rows)||
       cJSON_GetArraySize(rows)<1||cJSON_GetArraySize(rows)>PLAYER_INPUT_MAX)
        return fail(error,capacity,"Invalid touchscreen_inputs v1 patch-area plan");
    static const char *const keys[]={"parameter_id","axis","invert","deadband"};
    for(const cJSON *r=rows->child;r;r=r->next){
        const cJSON *id=cJSON_GetObjectItemCaseSensitive(r,"parameter_id"),*axis=cJSON_GetObjectItemCaseSensitive(r,"axis"),
                    *invert=cJSON_GetObjectItemCaseSensitive(r,"invert"),*dead=cJSON_GetObjectItemCaseSensitive(r,"deadband");
        if(!fields(r,keys,4)||!cJSON_IsString(id)||strlen(id->valuestring)<1||strlen(id->valuestring)>191||
           !cJSON_IsString(axis)||!cJSON_IsBool(invert)||!cJSON_IsNumber(dead)||!isfinite(dead->valuedouble)||dead->valuedouble<0||dead->valuedouble>.1)
            return fail(error,capacity,"Invalid touchscreen binding");
        player_screen_binding item={.parameter_index=count,.invert=cJSON_IsTrue(invert),.deadband=(float)dead->valuedouble};
        if(!strcmp(axis->valuestring,"x"))item.axis=PLAYER_SCREEN_X;
        else if(!strcmp(axis->valuestring,"y"))item.axis=PLAYER_SCREEN_Y;
        else if(!strcmp(axis->valuestring,"pressed"))item.axis=PLAYER_SCREEN_PRESSED;
        else return fail(error,capacity,"Unknown touchscreen axis");
        for(unsigned i=0;i<count;++i)if(!strcmp(id_at(context,i),id->valuestring)){item.parameter_index=i;break;}
        if(item.parameter_index==count)return fail(error,capacity,"Touchscreen parameter ID does not exist");
        for(unsigned i=0;i<plan->count;++i)if(plan->bindings[i].parameter_index==item.parameter_index)
            return fail(error,capacity,"Duplicate touchscreen parameter ID");
        plan->bindings[plan->count++]=item;
    }return true;
}
void player_screen_cancel(player_screen_state *s){s->captured=false;s->down=false;}
void player_screen_contact(player_screen_state *s,unsigned phase,int x,int y,unsigned w,unsigned h)
{
    bool inside=w>1&&h>1&&x>=0&&y>=0&&(unsigned)x<w&&(unsigned)y<h;
    if(phase==PLAYER_SCREEN_END){player_screen_cancel(s);return;}
    if(phase==PLAYER_SCREEN_BEGIN){s->captured=inside;s->down=inside;if(inside)memset(s->sent,0,sizeof s->sent);}
    else if(phase!=PLAYER_SCREEN_MOVE||!s->captured||!inside){player_screen_cancel(s);return;}
    if(s->down){s->x=(float)x/(float)(w-1);s->y=(float)y/(float)(h-1);}
}
void player_screen_reset_gates(const player_screen_plan *p,player_screen_state *s)
{for(unsigned i=0;i<p->count;++i)if(p->bindings[i].axis==PLAYER_SCREEN_PRESSED)s->sent[i]=false;}
bool player_screen_publish(const player_screen_plan *p,player_screen_state *s,bool (*publish)(unsigned,float))
{
    if(!publish)return p->count==0;
    bool accepted=true;
    /* Coordinates precede the gate even when parameter declarations are reordered. */
    for(unsigned pass=0;pass<2;++pass)for(unsigned i=0;i<p->count;++i){
        const player_screen_binding *b=&p->bindings[i];bool gate=b->axis==PLAYER_SCREEN_PRESSED;
        if(gate!=(pass==1)||(!gate&&!s->down))continue;
        float value=gate?(s->down?1.0f:0.0f):b->axis==PLAYER_SCREEN_X?s->x:s->y;
        if(b->invert)value=1.0f-value;
        if(s->sent[i]&&(value==s->last[i]||(!gate&&value!=0&&value!=1&&fabsf(value-s->last[i])<b->deadband)))continue;
        if(publish(b->parameter_index,value)){s->last[i]=value;s->sent[i]=true;}else accepted=false;
    }
    return accepted;
}
