/* SPDX-License-Identifier: MIT */
#pragma once
#include "rnbo_s3_module.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef struct cJSON cJSON;
enum { REMOTE_OSC_BYTES=1024, REMOTE_BATCH=8, REMOTE_ADDRESS_BYTES=256 };
typedef struct {unsigned index,kind;float value;} remote_update;
typedef struct {unsigned generation,count,epoch;remote_update updates[REMOTE_BATCH];} remote_batch;
typedef struct {const rnbo_s3_parameter_info *parameters;unsigned count,generation;const cJSON *plan;const cJSON *const *options;} remote_route;
/* Route points only into control-owned immutable metadata, protected by caller. */
bool remote_plan_valid(const remote_route *route);
const cJSON *remote_parameter_options(const remote_route *route,unsigned index);
bool remote_visible(const remote_route *route,unsigned index);
bool remote_resolve(const remote_route *route,const char *address,char type,float number,const char *label,remote_update *out);
bool remote_parameter_update(const remote_route *route,const char *id,bool normalized,char type,float number,const char *label,remote_update *out);
/* Full datagram admission before any event becomes visible. Immediate bundles
 * only, max8 leaf messages, max2 nested levels, no heap allocation. */
bool remote_decode(const remote_route *route,const uint8_t *bytes,size_t length,remote_batch *out);
/* Bound cJSON recursion before parsing an HTTP body, including quoted braces. */
bool remote_json_shallow(const char *bytes,size_t length);
