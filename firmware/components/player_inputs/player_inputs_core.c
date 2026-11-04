// SPDX-License-Identifier: MIT
#include "player_inputs.h"
#include "cJSON.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

static bool fail(char *error, size_t capacity, const char *message)
{ if(error && capacity)snprintf(error,capacity,"%s",message);return false; }
static bool fields(const cJSON *o, const char *const *allowed, unsigned count)
{
    if(!cJSON_IsObject(o))return false;
    for(const cJSON *p=o->child;p;p=p->next) {
        bool known=false;
        for(unsigned i=0;i<count;++i)if(!strcmp(p->string,allowed[i]))known=true;
        if(!known)return false;
        for(const cJSON *q=p->next;q;q=q->next)if(!strcmp(p->string,q->string))return false;
    }
    return true;
}
static bool number(const cJSON *o,const char *key,double low,double high,float *out)
{
    const cJSON *p=cJSON_GetObjectItemCaseSensitive(o,key);
    if(!cJSON_IsNumber(p)||!isfinite(p->valuedouble)||p->valuedouble<low||p->valuedouble>high)return false;
    *out=(float)p->valuedouble;return true;
}
static bool integer(const cJSON *o,const char *key,unsigned low,unsigned high,unsigned *out)
{
    float f;
    if(!number(o,key,(float)low,(float)high,&f)||f!=floorf(f))return false;
    /* Test the JSON double too, so near-integers cannot round into admission. */
    const cJSON *p=cJSON_GetObjectItemCaseSensitive(o,key);
    if(p->valuedouble!=(double)(unsigned)f)return false;
    *out=(unsigned)f;return true;
}
static int gpio_for_pin(const char *s)
{
    static const int map[]={1,2,3,4,5,6,43,44,7,8,9};
    if(!s)return -1;
    for(unsigned i=0;i<11;++i) {
        char alias[8];snprintf(alias,sizeof alias,"D%u",i);if(!strcmp(alias,s))return map[i];
        if(i<6||i>=8){snprintf(alias,sizeof alias,"A%u",i);if(!strcmp(alias,s))return map[i];}
        snprintf(alias,sizeof alias,"GPIO%d",map[i]);if(!strcmp(alias,s))return map[i];
    }
    return -1;
}
bool player_inputs_plan_parse(const cJSON *metadata,bool xiao,int bclk,int ws,int dout,
                             unsigned parameter_count,const char *(*id_at)(void *,unsigned),void *context,
                             player_input_plan *plan,char *error,size_t capacity)
{
    memset(plan,0,sizeof *plan);
    const cJSON *o=NULL;
    for(const cJSON *p=metadata?metadata->child:NULL;p;p=p->next)if(!strcmp(p->string,"physical_inputs")) {
        if(o)return fail(error,capacity,"Duplicate physical_inputs metadata");
        o=p;
    }
    if(!o)return true;
    if(!xiao)return fail(error,capacity,"Physical inputs v1 require the XIAO board profile; AMOLED pins are not interchangeable");
    static const char *const plan_fields[]={"version","board","bindings"};
    unsigned version;
    const cJSON *board=cJSON_GetObjectItemCaseSensitive(o,"board"),*rows=cJSON_GetObjectItemCaseSensitive(o,"bindings");
    if(!fields(o,plan_fields,3)||!integer(o,"version",1,1,&version)||!cJSON_IsString(board)||strcmp(board->valuestring,"xiao")||
       !cJSON_IsArray(rows)||cJSON_GetArraySize(rows)<1||cJSON_GetArraySize(rows)>PLAYER_INPUT_MAX)
        return fail(error,capacity,"Invalid physical_inputs v1 plan");
    for(const cJSON *row=rows->child;row;row=row->next) {
        player_input_binding b={0};
        const cJSON *id=cJSON_GetObjectItemCaseSensitive(row,"parameter_id"),*kind=cJSON_GetObjectItemCaseSensitive(row,"type"),
                    *pin=cJSON_GetObjectItemCaseSensitive(row,"pin"),*invert=cJSON_GetObjectItemCaseSensitive(row,"invert");
        if(!cJSON_IsString(id)||!cJSON_IsString(kind)||!cJSON_IsString(pin)||!cJSON_IsBool(invert))
            return fail(error,capacity,"Invalid physical input identity/type/pin/invert");
        b.gpio=gpio_for_pin(pin->valuestring);b.invert=cJSON_IsTrue(invert);
        if(b.gpio<0||b.gpio==3||b.gpio==bclk||b.gpio==ws||b.gpio==dout)
            return fail(error,capacity,"Physical input pin is unknown or reserved for audio/boot");
        /* Keep host/player v1 default-pin restrictions consistent even on a
         * custom audio build; widening this requires a new profile contract. */
        if(b.gpio>=7&&b.gpio<=9)return fail(error,capacity,"GPIO7..9 are reserved by the v1 XIAO input profile");
        snprintf(b.pin,sizeof b.pin,"%s",pin->valuestring);
        b.parameter_index=parameter_count;
        for(unsigned i=0;i<parameter_count;++i)if(!strcmp(id_at(context,i),id->valuestring)){b.parameter_index=i;break;}
        if(b.parameter_index==parameter_count)return fail(error,capacity,"Physical input parameter ID does not exist in the module");
        for(unsigned i=0;i<plan->count;++i)if(plan->bindings[i].gpio==b.gpio||plan->bindings[i].parameter_index==b.parameter_index)
            return fail(error,capacity,"Duplicate physical pin or parameter binding");
        static const char *const analog[]={"parameter_id","type","pin","invert","raw_min","raw_max","smooth_ms","deadband"};
        static const char *const digital[]={"parameter_id","type","pin","invert","pull","active_low","debounce_ms"};
        static const char *const touch[]={"parameter_id","type","pin","invert","threshold","hysteresis","debounce_ms"};
        if(!strcmp(kind->valuestring,"analog")) {
            b.kind=PLAYER_INPUT_ANALOG;
            if(b.gpio>6||!fields(row,analog,8)||!integer(row,"raw_min",0,4094,&b.raw_min)||!integer(row,"raw_max",1,4095,&b.raw_max)||
               b.raw_min>=b.raw_max||!number(row,"smooth_ms",0,1000,&b.smooth_ms)||!number(row,"deadband",0,0.1,&b.deadband))
                return fail(error,capacity,"Invalid analog input options");
        } else if(!strcmp(kind->valuestring,"digital")) {
            b.kind=PLAYER_INPUT_DIGITAL;
            const cJSON *pull=cJSON_GetObjectItemCaseSensitive(row,"pull"),*low=cJSON_GetObjectItemCaseSensitive(row,"active_low");
            if(!fields(row,digital,7)||!cJSON_IsString(pull)||!cJSON_IsBool(low)||!integer(row,"debounce_ms",0,1000,&b.debounce_ms))
                return fail(error,capacity,"Invalid digital input options");
            if(!strcmp(pull->valuestring,"up"))b.pull=1;
            else if(!strcmp(pull->valuestring,"down"))b.pull=-1;
            else if(strcmp(pull->valuestring,"none"))return fail(error,capacity,"Invalid digital pull direction");
            b.active_low=cJSON_IsTrue(low);
        } else if(!strcmp(kind->valuestring,"touch")) {
            b.kind=PLAYER_INPUT_TOUCH;
            if(b.gpio>6||!fields(row,touch,7)||!number(row,"threshold",0.001,1,&b.threshold)||
               !number(row,"hysteresis",0,0.99,&b.hysteresis)||b.hysteresis>=b.threshold||!integer(row,"debounce_ms",0,1000,&b.debounce_ms))
                return fail(error,capacity,"Invalid touch input options");
        } else return fail(error,capacity,"Unknown physical input type");
        plan->bindings[plan->count++]=b;
    }
    return true;
}
bool player_input_sample(const player_input_binding *b,player_input_state *s,uint32_t raw,int64_t now,float *out)
{
    s->raw=(float)raw;
    float value;
    if(b->kind==PLAYER_INPUT_ANALOG) {
        value=((float)raw-(float)b->raw_min)/(float)(b->raw_max-b->raw_min);
        value=fminf(1.0f,fmaxf(0.0f,value));
        if(b->invert)value=1.0f-value;
        float dt=s->sampled?(float)(now-s->previous_us)*0.001f:0.0f;
        if(!s->sampled||b->smooth_ms==0)s->filtered=value;
        else if(dt>0)s->filtered+=(value-s->filtered)*(dt/(b->smooth_ms+dt));
        s->sampled=true;s->previous_us=now;value=s->filtered;
        /* Snap settled endpoints so smoothing/deadband cannot prevent an exact
         * parameter minimum/maximum (especially important for gates/steps). */
        if((value<0.00001f&&((raw<=b->raw_min&&!b->invert)||(raw>=b->raw_max&&b->invert))))value=0;
        if((value>0.99999f&&((raw>=b->raw_max&&!b->invert)||(raw<=b->raw_min&&b->invert))))value=1;
        if(s->sent_once&&(value==s->sent || (value!=0&&value!=1&&fabsf(value-s->sent)<b->deadband)))return false;
    } else {
        bool active;
        if(b->kind==PLAYER_INPUT_TOUCH) {
            if(!raw)return false;
            if(s->calibration_samples<64) {
                s->baseline_sum+=(float)raw;
                if(++s->calibration_samples<64)return false;
                s->baseline=s->baseline_sum*(1.0f/64.0f);
            }
            float ratio=((float)raw-s->baseline)/s->baseline;
            s->touched=ratio>(s->touched?b->threshold-b->hysteresis:b->threshold);
            active=s->touched;
            /* Slow environmental tracking only while inactive; never learn a
             * held touch as the new baseline. */
            if(!active)s->baseline+=((float)raw-s->baseline)*0.001f;
        } else active=(raw!=0)!=b->active_low;
        if(b->invert)active=!active;
        if(!s->sampled||active!=s->candidate){s->candidate=active;s->candidate_us=now;}
        s->sampled=true;
        if(now-s->candidate_us<(int64_t)b->debounce_ms*1000)return false;
        if(s->stable_once&&s->stable==active)return false;
        s->stable_once=true;s->stable=active;value=active?1.0f:0.0f;s->filtered=value;
    }
    s->sent_once=true;s->sent=value;*out=value;return true;
}
