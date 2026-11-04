/* SPDX-License-Identifier: MIT */
/* FM1 RNBO visual-ui.h design: Copyright (c) 2026 Sebastian Tomczak and
 * contributors. Native LVGL renderer; see docs/patch-view.md for provenance. */
#include "patch_view.h"
#include "patch_layout.h"
#include <stdio.h>

static lv_obj_t *view;
static void (*select_parameter)(unsigned);
static unsigned selection=PATCH_NO_PARAMETER,page;
static const uint32_t RNBO_BLUE=0x40a0ff;

static void text(lv_draw_ctx_t *ctx,int x,int y,int width,const char *value,
                 uint32_t color,const lv_font_t *font)
{
    lv_draw_label_dsc_t d;lv_draw_label_dsc_init(&d);
    d.color=lv_color_hex(color);d.font=font;
    lv_area_t a={x,y,x+width-1,y+font->line_height-1};
    lv_draw_label(ctx,&d,&a,value,NULL);
}
static void draw(lv_event_t *event)
{
    lv_draw_ctx_t *ctx=lv_event_get_draw_ctx(event);
    lv_area_t area;lv_obj_get_coords(view,&area);
    const patch_layout *p=&rnbo_patch_layout;
    if (!p->node_count) {
        text(ctx,area.x1+4,area.y1+2,PATCH_WIDTH-8,p->fallback_reason,0xffffff,&rnbo_barlow_12);
        for (unsigned row=0;row<8;++row) {
            unsigned index=page*8+row;
            if (index>=p->parameter_count) break;
            text(ctx,area.x1+10,area.y1+25+(int)row*23,PATCH_WIDTH-20,
                 p->parameters[index].name,index==selection?0xffffff:RNBO_BLUE,&rnbo_barlow_16);
        }
        if (p->parameter_count>8) {
            char caption[64];snprintf(caption,sizeof caption,"< Previous        %u / %u        Next >",page+1,(p->parameter_count+7)/8);
            text(ctx,area.x1+8,area.y2-20,PATCH_WIDTH-16,caption,0xffffff,&rnbo_barlow_14);
        }
        return;
    }
    lv_draw_line_dsc_t line;lv_draw_line_dsc_init(&line);
    line.color=lv_color_white();line.width=1;
    for (unsigned i=0;i<p->segment_count;++i) {
        const patch_segment *s=&p->segments[i];
        lv_point_t a={area.x1+s->x1,area.y1+s->y1},b={area.x1+s->x2,area.y1+s->y2};
        lv_draw_line(ctx,&line,&a,&b);
    }
    for (unsigned i=0;i<p->node_count;++i) {
        const patch_node *n=&p->nodes[i];
        bool active=n->parameter!=PATCH_NO_PARAMETER && n->parameter==selection;
        uint32_t color=(n->flags&PATCH_NODE_GEN)?0xffffff:RNBO_BLUE;
        lv_draw_rect_dsc_t d;lv_draw_rect_dsc_init(&d);
        d.radius=0;d.bg_color=lv_color_hex(active?color:0);d.bg_opa=LV_OPA_COVER;
        d.border_color=lv_color_hex(color);d.border_width=1;
        lv_area_t box={area.x1+n->x,area.y1+n->y,area.x1+n->x+n->width-1,area.y1+n->y+n->height-1};
        lv_draw_rect(ctx,&d,&box);
        text(ctx,box.x1+3,box.y1+1,n->width-6,n->label,active?0:color,&rnbo_barlow_12);
        /* FM1's small black inlet/outlet notches. */
        d.border_width=0;d.bg_color=lv_color_black();
        if (n->inlets) {lv_area_t port={box.x1+3,box.y1,box.x1+4,box.y1};lv_draw_rect(ctx,&d,&port);}
        if (n->outlets) {lv_area_t port={box.x1+3,box.y2,box.x1+4,box.y2};lv_draw_rect(ctx,&d,&port);}
    }
}
static void clicked(lv_event_t *event)
{
    (void)event;
    lv_indev_t *input=lv_indev_get_act();if (!input) return;
    lv_point_t point;lv_indev_get_point(input,&point);
    lv_area_t area;lv_obj_get_coords(view,&area);point.x-=area.x1;point.y-=area.y1;
    const patch_layout *p=&rnbo_patch_layout;
    if (!p->node_count) {
        if (point.y>=PATCH_HEIGHT-24 && p->parameter_count>8) {
            unsigned pages=(p->parameter_count+7)/8;
            page=(point.x<PATCH_WIDTH/2)?(page+pages-1)%pages:(page+1)%pages;
            lv_obj_invalidate(view);return;
        }
        if (point.y>=25 && point.y<25+8*23) {
            unsigned index=page*8+(unsigned)(point.y-25)/23;
            if (index<p->parameter_count) select_parameter(index);
        }
        return;
    }
    for (unsigned pass=0;pass<2;++pass) for (unsigned i=0;i<p->node_count;++i) {
        const patch_node *n=&p->nodes[i];int pad=pass?6:0;
        if (n->parameter!=PATCH_NO_PARAMETER && point.x>=(int)n->x-pad && point.x<(int)(n->x+n->width)+pad &&
            point.y>=(int)n->y-pad && point.y<(int)(n->y+n->height)+pad) {
            select_parameter(n->parameter);return;
        }
    }
}
lv_obj_t *patch_view_create(lv_obj_t *parent,void (*select)(unsigned index))
{
    select_parameter=select;
    view=lv_obj_create(parent);lv_obj_remove_style_all(view);
    lv_obj_set_pos(view,16,64);lv_obj_set_size(view,PATCH_WIDTH,PATCH_HEIGHT);
    lv_obj_clear_flag(view,LV_OBJ_FLAG_SCROLLABLE);lv_obj_add_flag(view,LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(view,draw,LV_EVENT_DRAW_MAIN,NULL);
    lv_obj_add_event_cb(view,clicked,LV_EVENT_CLICKED,NULL);
    return view;
}
void patch_view_select(unsigned index)
{
    selection=index;
    if(index==PATCH_NO_PARAMETER)page=0;
    if(view)lv_obj_invalidate(view);
}
