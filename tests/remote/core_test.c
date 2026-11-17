/* Actual portable admission/parser; UBSan/bounds, no device or licensed DSP. */
#include "player_remote_core.h"
#include "cJSON.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static void be(uint8_t *p,uint32_t v){p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v;}
static size_t str(uint8_t *p,const char *s){size_t n=(strlen(s)+4)&~(size_t)3;memset(p,0,n);strcpy((char *)p,s);return n;}
static size_t msg(uint8_t *p,const char *address,char type,float v,const char *s){size_t n=str(p,address);char tag[]={',',type,0};n+=str(p+n,tag);if(type=='s')n+=str(p+n,s);else if(type=='f'||type=='i'){uint32_t bits;if(type=='f')memcpy(&bits,&v,4);else bits=(uint32_t)(int32_t)v;be(p+n,bits);n+=4;}return n;}
int main(void)
{
    assert(remote_json_shallow("{\"x\":\"[}]\"}",strlen("{\"x\":\"[}]\"}")));
    assert(!remote_json_shallow("[[[[[[[[[]]]]]]]]]",18));
    assert(!remote_json_shallow("{]",2));
    assert(!remote_json_shallow("{}\0x",4));
    rnbo_s3_parameter_info info[3]={
        {.id="cutoff",.name="Cutoff",.minimum=20,.maximum=20000},
        {.id="voice/gate",.name="Gate",.minimum=0,.maximum=1,.steps=2},
        {.id="mode",.name="Mode",.minimum=0,.maximum=2,.steps=3}};
    cJSON *plan=cJSON_Parse("{\"version\":1,\"parameters\":[{\"parameter_id\":\"cutoff\",\"osc\":{\"address\":\"/filter\",\"normalized\":true}},{\"parameter_id\":\"mode\",\"enum_values\":[\"sine\",\"saw\",\"square\"]}]}");
    remote_route r={.parameters=info,.count=3,.generation=17,.plan=plan};assert(remote_plan_valid(&r));
    remote_batch b;uint8_t p[1028];size_t n;
    n=msg(p,"/rnbo/inst/0/params/cutoff",'f',1200,NULL);assert(remote_decode(&r,p,n,&b));assert(b.count==1&&b.generation==17&&b.updates[0].value==1200&&b.updates[0].kind==RNBO_S3_PARAMETER_ACTUAL);
    n=msg(p,"/rnbo/inst/0/params/cutoff",'f',-10,NULL);assert(remote_decode(&r,p,n,&b)&&b.updates[0].value==20);
    n=msg(p,"/rnbo/inst/0/params/cutoff",'i',30000,NULL);assert(remote_decode(&r,p,n,&b)&&b.updates[0].value==20000);
    n=msg(p,"/rnbo/inst/0/params/voice/gate",'T',0,NULL);assert(remote_decode(&r,p,n,&b)&&b.updates[0].value==1);
    n=msg(p,"/rnbo/inst/0/params/voice/gate",'F',0,NULL);assert(remote_decode(&r,p,n,&b)&&b.updates[0].value==0);
    n=msg(p,"/rnbo/inst/0/params/cutoff/normalized",'f',1.5,NULL);assert(remote_decode(&r,p,n,&b)&&b.updates[0].value==1&&b.updates[0].kind==RNBO_S3_PARAMETER_NORMALIZED);
    n=msg(p,"/filter",'f',.25,NULL);assert(remote_decode(&r,p,n,&b)&&b.updates[0].value==.25f);
    n=msg(p,"/rnbo/inst/0/params/mode",'s',0,"saw");assert(remote_decode(&r,p,n,&b)&&b.updates[0].value==1);
    n=msg(p,"/rnbo/inst/0/params/mode",'s',0,"unknown");assert(!remote_decode(&r,p,n,&b)&&b.count==0);
    n=msg(p,"/rnbo/inst/0/params/mode",'f',1,NULL);assert(!remote_decode(&r,p,n,&b));
    const char *bad[]={"/rnbo/inst/1/params/cutoff","/rnbo/inst/0/params/Cutoff","/rnbo/inst/0/params/unknown","/rnbo/inst/0/params/cutoff/*","/rnbo/inst/0/params/cutoff/normalized/extra"};
    for(unsigned i=0;i<sizeof bad/sizeof*bad;++i){n=msg(p,bad[i],'f',0,NULL);assert(!remote_decode(&r,p,n,&b));}
    n=msg(p,"/rnbo/inst/0/params/cutoff",'f',NAN,NULL);assert(!remote_decode(&r,p,n,&b));
    n=msg(p,"/rnbo/inst/0/params/cutoff",'f',INFINITY,NULL);assert(!remote_decode(&r,p,n,&b));
    n=msg(p,"/rnbo/inst/0/params/cutoff/normalized",'i',1,NULL);assert(!remote_decode(&r,p,n,&b));
    n=msg(p,"/filter",'f',.5,NULL);p[n++]=0;assert(!remote_decode(&r,p,n,&b));
    n=msg(p,"/filter",'f',.5,NULL);p[9]=99;assert(!remote_decode(&r,p,n,&b)); /* invalid type padding */
    memset(p,0,sizeof p);memcpy(p,"#bundle",7);be(p+12,1);size_t at=16;
    for(unsigned i=0;i<8;++i){size_t length=msg(p+at+4,"/filter",'f',.5,NULL);be(p+at,(uint32_t)length);at+=4+length;}
    assert(remote_decode(&r,p,at,&b)&&b.count==8); /* repeated updates preserved */
    be(p+12,2);assert(!remote_decode(&r,p,at,&b));be(p+12,1);
    size_t extra=msg(p+at+4,"/filter",'f',.5,NULL);be(p+at,(uint32_t)extra);assert(!remote_decode(&r,p,at+4+extra,&b)&&b.count==0);
    be(p+16,10000);assert(!remote_decode(&r,p,at,&b)&&b.count==0);
    cJSON_Delete(plan);
    r.plan=cJSON_Parse("{\"version\":1,\"parameters\":[{\"parameter_id\":\"voice/gate\",\"visible\":false}]}");assert(remote_plan_valid(&r));n=msg(p,"/rnbo/inst/0/params/voice/gate",'f',1,NULL);assert(!remote_decode(&r,p,n,&b));cJSON_Delete((cJSON *)r.plan);r.plan=NULL;
    strcpy(info[1].id,"cutoff/normalized");assert(!remote_plan_valid(&r));strcpy(info[1].id,"voice/gate");
    r.plan=cJSON_Parse("{\"version\":1,\"parameters\":[{\"parameter_id\":\"cutoff\",\"osc\":{\"address\":\"/a\",\"normalized\":false}},{\"parameter_id\":\"mode\",\"osc\":{\"address\":\"/a\",\"normalized\":false}}]}");assert(!remote_plan_valid(&r));cJSON_Delete((cJSON *)r.plan);r.plan=NULL;
    /* Deterministic malformed/truncated datagram corpus. */
    uint32_t seed=123;for(unsigned i=0;i<30000;++i){size_t length=i%1028;for(size_t j=0;j<length;++j){seed=seed*1664525+1013904223;p[j]=(uint8_t)(seed>>24);}assert(!remote_decode(&r,p,length,&b));}
    puts("OSC address/types/clipping/enums/bundles/fuzz PASS");return 0;
}
