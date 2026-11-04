/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>

/* Display-owned metadata, never pointers from a module image. */
enum { PATCH_WIDTH=336, PATCH_HEIGHT=232, PATCH_NO_PARAMETER=255,
       PATCH_MAX_NODES=96, PATCH_MAX_SEGMENTS=384, PATCH_NODE_GEN=1 };
typedef struct {
    uint16_t x,y,width,height;
    uint8_t parameter,inlets,outlets,flags;
    char label[32];
} patch_node;
typedef struct {uint16_t x1,y1,x2,y2;} patch_segment;
typedef struct {char name[96],unit[32];} patch_parameter;
typedef struct {
    const char *title,*fallback_reason,*source_sha256;
    uint16_t node_count,segment_count,parameter_count;
    const patch_node *nodes;
    const patch_segment *segments;
    const patch_parameter *parameters;
} patch_layout;
#ifdef RNBO_S3_PLAYER
extern patch_layout rnbo_patch_layout;
typedef struct cJSON cJSON;
/* Internal player layout builder. Invalid visuals produce a parameter-list
 * fallback. The returned allocation owns every pointer in the layout. */
int patch_layout_build_player(const char *title,const char *source_sha256,
                              const cJSON *visual,const patch_parameter *labels,
                              unsigned count,patch_layout *layout,void **owned);
void patch_layout_free_player(void *owned);
#else
extern const patch_layout rnbo_patch_layout;
#endif
