// SPDX-License-Identifier: MIT
#include "patch_layout.h"
#include "cJSON.h"
#include "esp_err.h"
#include "esp_heap_caps.h"
#include <stdbool.h>
#include <math.h>
#include <string.h>

enum { PLAYER_MAX_PARAMETERS=32 };
typedef struct {
    char title[64],source_sha256[65],reason[96];
    patch_parameter parameters[PLAYER_MAX_PARAMETERS];
    patch_node nodes[PATCH_MAX_NODES];
    patch_segment segments[PATCH_MAX_SEGMENTS];
} owned_player_layout;

patch_layout rnbo_patch_layout={
    .title="RNBO Player",.source_sha256="none",.fallback_reason="Upload an RNBO patch",
};

static void copy_text(char *out,size_t capacity,const char *input)
{
    if(!input)input="";
    size_t count=0;
    while(count+1<capacity && input[count]){out[count]=input[count];++count;}
    out[count]='\0';
}
static bool integer(const cJSON *value,unsigned maximum,unsigned *out)
{
    if(!cJSON_IsNumber(value) || !isfinite(value->valuedouble) || value->valuedouble<0 ||
       value->valuedouble>maximum || floor(value->valuedouble)!=value->valuedouble)return false;
    *out=(unsigned)value->valuedouble;return true;
}
static bool field(const cJSON *object,const char *name,unsigned maximum,unsigned *out)
{
    return integer(cJSON_GetObjectItemCaseSensitive(object,name),maximum,out);
}
static bool visual_layout(const cJSON *visual,unsigned count,owned_player_layout *storage,
                          patch_layout *layout)
{
    if(!cJSON_IsObject(visual))return false;
    const cJSON *format=cJSON_GetObjectItemCaseSensitive(visual,"format");
    unsigned width,height;
    if(!cJSON_IsString(format) || strcmp(format->valuestring,"rnbo-s3-visual-v1") ||
       !field(visual,"width",PATCH_WIDTH,&width) || width!=PATCH_WIDTH ||
       !field(visual,"height",PATCH_HEIGHT,&height) || height!=PATCH_HEIGHT ||
       !cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(visual,"available")))return false;
    const cJSON *nodes=cJSON_GetObjectItemCaseSensitive(visual,"nodes");
    const cJSON *segments=cJSON_GetObjectItemCaseSensitive(visual,"segments");
    const cJSON *parameters=cJSON_GetObjectItemCaseSensitive(visual,"parameters");
    if(!cJSON_IsArray(nodes) || !cJSON_IsArray(segments) || !cJSON_IsArray(parameters) ||
       cJSON_GetArraySize(parameters)!=(int)count)return false;
    int nn=cJSON_GetArraySize(nodes),ns=cJSON_GetArraySize(segments);
    if(nn<1 || nn>PATCH_MAX_NODES || ns>PATCH_MAX_SEGMENTS)return false;
    for(int i=0;i<nn;++i){
        const cJSON *node=cJSON_GetArrayItem(nodes,i);
        unsigned x,y,w,h,parameter,inlets,outlets,flags;
        const cJSON *label=cJSON_GetObjectItemCaseSensitive(node,"label");
        if(!cJSON_IsObject(node) || !field(node,"x",PATCH_WIDTH-1,&x) ||
           !field(node,"y",PATCH_HEIGHT-1,&y) || !field(node,"width",PATCH_WIDTH,&w) ||
           !field(node,"height",PATCH_HEIGHT,&h) || w<7 || h<2 ||
           x+w>PATCH_WIDTH || y+h>PATCH_HEIGHT ||
           !field(node,"parameter",PATCH_NO_PARAMETER,&parameter) ||
           (parameter!=PATCH_NO_PARAMETER && parameter>=count) ||
           !field(node,"inlets",32,&inlets) || !field(node,"outlets",32,&outlets) ||
           !field(node,"flags",PATCH_NODE_GEN,&flags) || !cJSON_IsString(label) ||
           strlen(label->valuestring)>31)return false;
        storage->nodes[i]=(patch_node){(uint16_t)x,(uint16_t)y,(uint16_t)w,(uint16_t)h,
                                      (uint8_t)parameter,(uint8_t)inlets,(uint8_t)outlets,(uint8_t)flags,{0}};
        copy_text(storage->nodes[i].label,sizeof(storage->nodes[i].label),label->valuestring);
    }
    for(int i=0;i<ns;++i){
        const cJSON *segment=cJSON_GetArrayItem(segments,i);
        unsigned values[4];
        if(!cJSON_IsArray(segment) || cJSON_GetArraySize(segment)!=4)return false;
        for(int j=0;j<4;++j)
            if(!integer(cJSON_GetArrayItem(segment,j),(j&1)?PATCH_HEIGHT-1:PATCH_WIDTH-1,&values[j]))return false;
        storage->segments[i]=(patch_segment){(uint16_t)values[0],(uint16_t)values[1],(uint16_t)values[2],(uint16_t)values[3]};
    }
    layout->node_count=(uint16_t)nn;layout->segment_count=(uint16_t)ns;
    layout->nodes=storage->nodes;layout->segments=storage->segments;
    return true;
}

int patch_layout_build_player(const char *title,const char *source_sha256,const cJSON *visual,
                              const patch_parameter *labels,unsigned count,
                              patch_layout *layout,void **owned)
{
    if(!layout || !owned || count>PLAYER_MAX_PARAMETERS || (count && !labels))return ESP_ERR_INVALID_ARG;
    *owned=NULL;memset(layout,0,sizeof(*layout));
    owned_player_layout *storage=heap_caps_malloc(sizeof(*storage),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    if(!storage)return ESP_ERR_NO_MEM;
    memset(storage,0,sizeof(*storage));
    copy_text(storage->title,sizeof(storage->title),title && title[0]?title:"RNBO Player");
    copy_text(storage->source_sha256,sizeof(storage->source_sha256),source_sha256?source_sha256:"none");
    copy_text(storage->reason,sizeof(storage->reason),"Patch view unavailable / Parameters");
    for(unsigned i=0;i<count;++i){
        copy_text(storage->parameters[i].name,sizeof(storage->parameters[i].name),labels[i].name);
        copy_text(storage->parameters[i].unit,sizeof(storage->parameters[i].unit),labels[i].unit);
    }
    *layout=(patch_layout){.title=storage->title,.source_sha256=storage->source_sha256,
        .fallback_reason=storage->reason,.parameter_count=(uint16_t)count,.parameters=storage->parameters};
    if(!visual_layout(visual,count,storage,layout)){
        layout->node_count=0;layout->segment_count=0;layout->nodes=NULL;layout->segments=NULL;
    }
    *owned=storage;return ESP_OK;
}
void patch_layout_free_player(void *owned){heap_caps_free(owned);}
