/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "board_display.h"
#include "patch_view.h"
#include "patch_layout.h"
#include "touch_display.h"
#include "bsp/esp-bsp.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

enum { MAX_PARAMETER_ROWS=128, PARAMETERS_PER_BANK=8, METER_SEGMENTS=28, PARAMETER_BAR_BOTTOM=188 };
static board_display_actions actions;
static lv_obj_t *status_label,*volume_label,*volume_slider,*render_label,*battery_label;
static lv_obj_t *patch_panel,*params_panel,*params_caption,*page_label,*meter,*meter_label,*transport_caption;
static float parameter_values[MAX_PARAMETER_ROWS],parameter_normalized[MAX_PARAMETER_ROWS];
static bool parameter_available[MAX_PARAMETER_ROWS];
static bool ready,params_visible,parameter_editing;
static bool transport_paused=true;
static unsigned parameter_bank;
static int last_column=-1,last_parameter_value;
static unsigned current_volume=100,selected=PATCH_NO_PARAMETER;
static float meter_db=-60,hold_db=-60;
static uint32_t meter_tick,hold_tick,battery_tick,cpu_tick;

static void set_text(lv_obj_t *object,const char *text)
{
    if (strcmp(lv_label_get_text(object),text)) lv_label_set_text(object,text);
}
static lv_obj_t *label(lv_obj_t *parent,const char *text,int x,int y,int width,const lv_font_t *font)
{
    lv_obj_t *o=lv_label_create(parent);lv_label_set_text(o,text);
    lv_obj_set_pos(o,x,y);lv_obj_set_width(o,width);lv_label_set_long_mode(o,LV_LABEL_LONG_DOT);
    lv_obj_set_style_text_color(o,lv_color_white(),0);lv_obj_set_style_text_font(o,font,0);
    lv_obj_clear_flag(o,LV_OBJ_FLAG_CLICKABLE);return o;
}
static void slider_style(lv_obj_t *slider)
{
    lv_obj_set_style_bg_color(slider,lv_color_hex(0x404040),LV_PART_MAIN);
    lv_obj_set_style_bg_color(slider,lv_color_hex(0x40a0ff),LV_PART_INDICATOR);
    lv_obj_set_style_bg_color(slider,lv_color_white(),LV_PART_KNOB);
    lv_obj_set_style_pad_all(slider,6,LV_PART_KNOB);
    lv_obj_set_ext_click_area(slider,7);
}
static void refresh_parameters(void)
{
    if (!actions.parameter_value) return;
    for (unsigned i=0;i<rnbo_patch_layout.parameter_count && i<MAX_PARAMETER_ROWS;++i) {
        float actual,normalized;
        if (actions.parameter_value(i,&actual,&normalized)) {
            parameter_values[i]=actual;parameter_available[i]=true;
            if (!parameter_editing || last_column<0 || i!=parameter_bank*PARAMETERS_PER_BANK+(unsigned)last_column)
                parameter_normalized[i]=fmaxf(0,fminf(1,normalized));
        } else parameter_available[i]=false;
    }
    if (params_panel) lv_obj_invalidate(params_panel);
}
static void show_page(bool parameters)
{
    params_visible=parameters;
    if (parameters) {
        lv_obj_add_flag(patch_panel,LV_OBJ_FLAG_HIDDEN);lv_obj_clear_flag(params_panel,LV_OBJ_FLAG_HIDDEN);
        set_text(params_caption,"Patch");set_text(page_label,"RNBO / PARAMS");refresh_parameters();
    } else {
        lv_obj_add_flag(params_panel,LV_OBJ_FLAG_HIDDEN);lv_obj_clear_flag(patch_panel,LV_OBJ_FLAG_HIDDEN);
        patch_view_select(selected);
        set_text(params_caption,"Params");set_text(page_label,"RNBO / MAIN");
    }
}
static void select_parameter(unsigned index)
{
    if (index>=rnbo_patch_layout.parameter_count || index>=MAX_PARAMETER_ROWS || !actions.parameter) return;
    selected=index;parameter_bank=index/PARAMETERS_PER_BANK;patch_view_select(index);show_page(true);
}
static void toggle_page(lv_event_t *event){(void)event;show_page(!params_visible);}
static void transport_pressed(lv_event_t *event)
{
    (void)event;
    if (transport_paused) actions.resume();
    else {actions.panic();set_text(status_label,"Paused");}
}
static void volume_changed(lv_event_t *event)
{
    (void)event;unsigned value=(unsigned)lv_slider_get_value(volume_slider);
    if (actions.volume(value)) current_volume=value;
}
static unsigned visible_parameters(void)
{
    unsigned left=rnbo_patch_layout.parameter_count-parameter_bank*PARAMETERS_PER_BANK;
    return left<PARAMETERS_PER_BANK?left:PARAMETERS_PER_BANK;
}
static int parameter_bar_top(void){return rnbo_patch_layout.parameter_count>PARAMETERS_PER_BANK?40:24;}
static void parameter_write(unsigned column,int value)
{
    unsigned index=parameter_bank*PARAMETERS_PER_BANK+column;
    if (actions.parameter(index,(float)value/1000.0f)) {
        parameter_normalized[index]=(float)value/1000.0f;selected=index;
    } else set_text(status_label,"Resume to edit / queue busy");
}
/* One shared touch surface retains the press while moving between bars.
 * Interpolate skipped columns, so a fast sweep still edits every crossed bar. */
static void parameter_touch(lv_event_t *event)
{
    lv_event_code_t code=lv_event_get_code(event);
    if (code==LV_EVENT_RELEASED || code==LV_EVENT_PRESS_LOST) {
        parameter_editing=false;last_column=-1;refresh_parameters();return;
    }
    if (!actions.parameter || lv_obj_has_state(params_panel,LV_STATE_DISABLED) || !visible_parameters()) return;
    lv_indev_t *input=lv_indev_get_act();if (!input) return;
    lv_point_t point;lv_indev_get_point(input,&point);lv_area_t area;lv_obj_get_coords(params_panel,&area);
    int x=point.x-area.x1,y=point.y-area.y1;
    if (code==LV_EVENT_PRESSED) {
        last_column=-1;
        if (rnbo_patch_layout.parameter_count>PARAMETERS_PER_BANK && y<18) {
            parameter_editing=false;
            unsigned banks=(rnbo_patch_layout.parameter_count+PARAMETERS_PER_BANK-1)/PARAMETERS_PER_BANK;
            parameter_bank=x<PATCH_WIDTH/2?(parameter_bank+banks-1)%banks:(parameter_bank+1)%banks;
            lv_obj_invalidate(params_panel);return;
        }
        parameter_editing=true;
    } else if (code!=LV_EVENT_PRESSING || !parameter_editing) return;
    if (x<0) x=0;
    if (x>=PATCH_WIDTH) x=PATCH_WIDTH-1;
    int column=x*(int)visible_parameters()/PATCH_WIDTH;
    int top=parameter_bar_top(),value=(PARAMETER_BAR_BOTTOM-y)*1000/(PARAMETER_BAR_BOTTOM-top);
    if (value<0) value=0;
    if (value>1000) value=1000;
    if (last_column<0 || column==last_column) {
        if (last_column<0 || value!=last_parameter_value) parameter_write((unsigned)column,value);
    } else {
        int distance=column>last_column?column-last_column:last_column-column;
        int direction=column>last_column?1:-1;
        for (int step=1;step<=distance;++step)
            parameter_write((unsigned)(last_column+step*direction),last_parameter_value+(value-last_parameter_value)*step/distance);
    }
    last_column=column;last_parameter_value=value;lv_obj_invalidate(params_panel);
}
static void parameter_text(lv_draw_ctx_t *ctx,int x,int y,int width,const char *value,uint32_t color)
{
    lv_draw_label_dsc_t d;lv_draw_label_dsc_init(&d);d.font=&rnbo_barlow_12;d.color=lv_color_hex(color);d.align=LV_TEXT_ALIGN_CENTER;
    lv_area_t a={x,y,x+width-1,y+rnbo_barlow_12.line_height-1};lv_draw_label(ctx,&d,&a,value,NULL);
}
static void parameters_draw(lv_event_t *event)
{
    lv_draw_ctx_t *ctx=lv_event_get_draw_ctx(event);lv_area_t area;lv_obj_get_coords(params_panel,&area);
    unsigned count=visible_parameters();bool disabled=lv_obj_has_state(params_panel,LV_STATE_DISABLED);
    if (!count) {parameter_text(ctx,area.x1,area.y1+8,PATCH_WIDTH,"No input parameters",0xffffff);return;}
    if (rnbo_patch_layout.parameter_count>PARAMETERS_PER_BANK) {
        char bank[48];snprintf(bank,sizeof bank,"<     %u / %u     >",parameter_bank+1,(rnbo_patch_layout.parameter_count+7)/8);
        parameter_text(ctx,area.x1,area.y1,PATCH_WIDTH,bank,0xffffff);
    }
    int top=parameter_bar_top();
    for (unsigned column=0;column<count;++column) {
        unsigned index=parameter_bank*PARAMETERS_PER_BANK+column;
        int x=area.x1+(int)(column*PATCH_WIDTH/count),width=(int)((column+1)*PATCH_WIDTH/count)-(x-area.x1);
        char value[96],first[32],second[32];
        if (parameter_available[index]) snprintf(value,sizeof value,"%.4g%s",(double)parameter_values[index],rnbo_patch_layout.parameters[index].unit);
        else snprintf(value,sizeof value,"--");
        parameter_text(ctx,x,area.y1+top-21,width,value,0xffffff);
        lv_draw_rect_dsc_t d;lv_draw_rect_dsc_init(&d);d.radius=0;d.bg_opa=LV_OPA_COVER;
        d.bg_color=lv_color_hex(0x101820);d.border_color=lv_color_hex(disabled?0x48505a:index==selected?0xffffff:0x40a0ff);d.border_width=1;
        lv_area_t box={x+3,area.y1+top,x+width-4,area.y1+PARAMETER_BAR_BOTTOM};lv_draw_rect(ctx,&d,&box);
        int height=(int)lroundf(parameter_normalized[index]*(PARAMETER_BAR_BOTTOM-top-1));
        if (height>0) {
            d.border_width=0;d.bg_color=lv_color_hex(disabled?0x384653:0x40a0ff);
            lv_area_t fill={box.x1+1,box.y2-height,box.x2-1,box.y2-1};lv_draw_rect(ctx,&d,&fill);
        }
        const char *name=rnbo_patch_layout.parameters[index].name,*split=strchr(name,'-');
        int limit=(width-4)/6;if (limit>31) limit=31;
        int length=split?(int)(split-name):(int)strlen(name);
        snprintf(first,sizeof first,"%.*s",length<limit?length:limit,name);
        snprintf(second,sizeof second,"%.*s",limit,split?split+1:name+strlen(first));
        parameter_text(ctx,x,area.y1+195,width,first,disabled?0x8d9aa7:0x40a0ff);
        parameter_text(ctx,x,area.y1+210,width,second,disabled?0x8d9aa7:0x40a0ff);
    }
}
static lv_obj_t *button(lv_obj_t *screen,const char *text,int x,int y,int width,int height,lv_event_cb_t callback)
{
    lv_obj_t *o=lv_btn_create(screen);lv_obj_remove_style_all(o);
    lv_obj_set_pos(o,x,y);lv_obj_set_size(o,width,height);
    lv_obj_set_style_bg_color(o,lv_color_black(),0);lv_obj_set_style_bg_opa(o,LV_OPA_COVER,0);
    lv_obj_set_style_border_color(o,lv_color_white(),0);lv_obj_set_style_border_width(o,1,0);
    lv_obj_set_style_bg_color(o,lv_color_hex(0x204060),LV_STATE_PRESSED);
    lv_obj_set_style_text_color(o,lv_color_white(),0);lv_obj_set_style_text_font(o,&rnbo_barlow_16,0);
    lv_obj_add_event_cb(o,callback,LV_EVENT_CLICKED,NULL);
    lv_obj_t *caption=lv_label_create(o);lv_label_set_text(caption,text);lv_obj_center(caption);return o;
}
static void meter_draw(lv_event_t *event)
{
    lv_draw_ctx_t *ctx=lv_event_get_draw_ctx(event);lv_area_t area;lv_obj_get_coords(meter,&area);
    lv_draw_rect_dsc_t d;lv_draw_rect_dsc_init(&d);d.radius=0;d.bg_opa=LV_OPA_COVER;d.border_width=0;
    for (unsigned i=0;i<METER_SEGMENTS;++i) {
        bool lit=meter_db>-60.0f+(float)i*60.0f/METER_SEGMENTS;
        uint32_t color=i>=26?0xff5050:i>=23?0xf2cd55:0x5acb85;
        d.bg_color=lv_color_hex(lit?color:0x242a29);
        lv_area_t segment={area.x1+(int)i*12,area.y1,area.x1+(int)i*12+10,area.y2};
        lv_draw_rect(ctx,&d,&segment);
    }
    if (hold_db>-60) {
        int x=(int)lroundf((hold_db+60)*335.0f/60.0f);
        if (x<0) x=0;
        if (x>335) x=335;
        d.bg_color=lv_color_white();lv_area_t peak={area.x1+x,area.y1,area.x1+x,area.y2};
        lv_draw_rect(ctx,&d,&peak);
    }
}
esp_err_t board_display_start(const board_display_actions *callbacks)
{
    if (!callbacks || !callbacks->panic || !callbacks->resume || !callbacks->volume || !callbacks->source_label)
        return ESP_ERR_INVALID_ARG;
    if (rnbo_patch_layout.parameter_count>MAX_PARAMETER_ROWS) return ESP_ERR_INVALID_ARG;
    actions=*callbacks;current_volume=callbacks->initial_volume;
    esp_err_t result=touch_display_start();if (result!=ESP_OK) return result;
    if (!bsp_display_lock(2000)) return ESP_ERR_TIMEOUT;
    lv_obj_t *screen=lv_scr_act();
    lv_obj_set_style_bg_color(screen,lv_color_black(),0);lv_obj_clear_flag(screen,LV_OBJ_FLAG_SCROLLABLE);
    label(screen,rnbo_patch_layout.title,16,12,250,&rnbo_barlow_22);
    battery_label=label(screen,"USB",286,18,66,&rnbo_barlow_14);
    status_label=label(screen,"Starting",16,40,180,&rnbo_barlow_14);
    page_label=label(screen,"RNBO / MAIN",222,40,130,&rnbo_barlow_14);
    lv_obj_set_style_text_align(page_label,LV_TEXT_ALIGN_RIGHT,0);
    patch_panel=patch_view_create(screen,select_parameter);
    params_panel=lv_obj_create(screen);lv_obj_remove_style_all(params_panel);
    lv_obj_set_pos(params_panel,16,64);lv_obj_set_size(params_panel,PATCH_WIDTH,PATCH_HEIGHT);
    lv_obj_clear_flag(params_panel,LV_OBJ_FLAG_SCROLLABLE);lv_obj_add_flag(params_panel,LV_OBJ_FLAG_CLICKABLE|LV_OBJ_FLAG_PRESS_LOCK);
    lv_obj_add_event_cb(params_panel,parameters_draw,LV_EVENT_DRAW_MAIN,NULL);
    lv_obj_add_event_cb(params_panel,parameter_touch,LV_EVENT_PRESSED,NULL);
    lv_obj_add_event_cb(params_panel,parameter_touch,LV_EVENT_PRESSING,NULL);
    lv_obj_add_event_cb(params_panel,parameter_touch,LV_EVENT_RELEASED,NULL);
    lv_obj_add_event_cb(params_panel,parameter_touch,LV_EVENT_PRESS_LOST,NULL);
    lv_obj_add_flag(params_panel,LV_OBJ_FLAG_HIDDEN);
    render_label=label(screen,"CPU --",16,303,336,&rnbo_barlow_14);
    volume_label=label(screen,"Volume",16,329,170,&rnbo_barlow_16);
    meter_label=label(screen,"OUT -inf dBFS",192,331,160,&rnbo_barlow_12);
    lv_obj_set_style_text_align(meter_label,LV_TEXT_ALIGN_RIGHT,0);
    meter=lv_obj_create(screen);lv_obj_remove_style_all(meter);lv_obj_set_pos(meter,16,353);lv_obj_set_size(meter,336,9);
    lv_obj_clear_flag(meter,LV_OBJ_FLAG_SCROLLABLE|LV_OBJ_FLAG_CLICKABLE);lv_obj_add_event_cb(meter,meter_draw,LV_EVENT_DRAW_MAIN,NULL);
    volume_slider=lv_slider_create(screen);lv_obj_set_pos(volume_slider,24,376);lv_obj_set_size(volume_slider,320,12);
    slider_style(volume_slider);lv_obj_set_style_bg_color(volume_slider,lv_color_white(),LV_PART_INDICATOR);
    lv_slider_set_range(volume_slider,0,100);lv_slider_set_value(volume_slider,(int)current_volume,LV_ANIM_OFF);
    lv_obj_add_event_cb(volume_slider,volume_changed,LV_EVENT_VALUE_CHANGED,NULL);
    lv_obj_t *transport_button=button(screen,"Resume",16,405,216,31,transport_pressed);
    transport_caption=lv_obj_get_child(transport_button,0);
    lv_obj_t *params_button=button(screen,"Params",248,405,104,31,toggle_page);
    params_caption=lv_obj_get_child(params_button,0);
    if (!actions.parameter || !actions.parameter_value || !rnbo_patch_layout.parameter_count) lv_obj_add_state(params_button,LV_STATE_DISABLED);
    refresh_parameters();meter_tick=hold_tick=battery_tick=cpu_tick=lv_tick_get();ready=true;
    bsp_display_unlock();return bsp_display_brightness_set(55);
}
void board_display_update(bool muted,bool fault,unsigned volume,uint32_t render_us,uint32_t peak_us,unsigned output_peak_q15)
{
    if (!ready) return;
    touch_battery battery={.percent=-1};bool refresh_battery=lv_tick_elaps(battery_tick)>=1000;
    esp_err_t battery_result=ESP_OK;
    if (refresh_battery) {battery_result=touch_display_battery(&battery);battery_tick=lv_tick_get();}
    if (!bsp_display_lock(20)) return;
    transport_paused=muted || fault;
    set_text(transport_caption,transport_paused?"Resume":"Pause");
    set_text(status_label,fault?"Audio fault / paused":muted?"Paused":"Playing");
    lv_obj_set_style_text_color(status_label,lv_color_hex(fault?0xff6060:0xffffff),0);
    char text[112];current_volume=volume;
    snprintf(text,sizeof text,"Volume  %u%%",volume);set_text(volume_label,text);
    if (!lv_obj_has_state(volume_slider,LV_STATE_PRESSED)) lv_slider_set_value(volume_slider,(int)volume,LV_ANIM_OFF);
    if (lv_tick_elaps(cpu_tick)>=1000) {
        unsigned current=(unsigned)(((uint64_t)render_us*44100u)/(256u*1000u));
        unsigned peak=(unsigned)(((uint64_t)peak_us*44100u)/(256u*1000u));
        snprintf(text,sizeof text,"CPU %u.%u%%      Peak %u.%u%%      44.1 kHz",current/10,current%10,peak/10,peak%10);
        set_text(render_label,text);cpu_tick=lv_tick_get();
    }
    if (params_visible) refresh_parameters();
    if (muted || fault) {parameter_editing=false;last_column=-1;lv_obj_add_state(params_panel,LV_STATE_DISABLED);}
    else lv_obj_clear_state(params_panel,LV_STATE_DISABLED);
    float elapsed=(float)lv_tick_elaps(meter_tick)*0.001f;meter_tick=lv_tick_get();
    float input_db=output_peak_q15?20.0f*log10f(fminf((float)output_peak_q15,32767.0f)/32767.0f):-60.0f;
    if (input_db< -60) input_db=-60;
    if (muted || fault) meter_db=hold_db=-60;
    else {
        meter_db=fmaxf(input_db,meter_db-24.0f*elapsed);
        if (input_db>=hold_db) {hold_db=input_db;hold_tick=lv_tick_get();}
        else if (lv_tick_elaps(hold_tick)>1000) hold_db=fmaxf(meter_db,hold_db-32.0f*elapsed);
    }
    if (meter_db<=-60) snprintf(text,sizeof text,output_peak_q15 && !muted && !fault?"OUT <-60 dBFS":"OUT -inf dBFS");
    else snprintf(text,sizeof text,"OUT %.1f dBFS",(double)meter_db);
    set_text(meter_label,text);lv_obj_invalidate(meter);
    if (refresh_battery) {
        if (battery_result!=ESP_OK) snprintf(text,sizeof text,"Power --");
        else if (battery.present && battery.percent>=0) snprintf(text,sizeof text,"%d%%%s",battery.percent,battery.charging?" +":"");
        else snprintf(text,sizeof text,battery.usb?"USB":"Battery");
        set_text(battery_label,text);
    }
    bsp_display_unlock();
}
