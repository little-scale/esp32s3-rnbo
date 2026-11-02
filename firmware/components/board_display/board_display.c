/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "board_display.h"
#include "patch_view.h"
#include "patch_layout.h"
#include "touch_display.h"
#include "bsp/esp-bsp.h"
#include <math.h>
#include <stdio.h>

static board_display_actions actions;
static lv_obj_t *status_label,*control_label,*control_slider,*render_label,*battery_label,*volume_button;
static bool ready;
static unsigned selected=PATCH_NO_PARAMETER,current_volume=100;

static lv_obj_t *label(lv_obj_t *parent,const char *text,int x,int y,int width,const lv_font_t *font)
{
    lv_obj_t *o=lv_label_create(parent);lv_label_set_text(o,text);
    lv_obj_set_pos(o,x,y);lv_obj_set_width(o,width);lv_label_set_long_mode(o,LV_LABEL_LONG_DOT);
    lv_obj_set_style_text_color(o,lv_color_white(),0);lv_obj_set_style_text_font(o,font,0);
    lv_obj_clear_flag(o,LV_OBJ_FLAG_CLICKABLE);return o;
}
static void control_text(void)
{
    char text[144];float actual,normalized;
    if (selected<rnbo_patch_layout.parameter_count && actions.parameter_value &&
        actions.parameter_value(selected,&actual,&normalized)) {
        const patch_parameter *p=&rnbo_patch_layout.parameters[selected];
        snprintf(text,sizeof text,"%s  %.4g %s",p->name,(double)actual,p->unit);
        if (!lv_obj_has_state(control_slider,LV_STATE_PRESSED))
            lv_slider_set_value(control_slider,(int)lroundf(normalized*1000),LV_ANIM_OFF);
    } else snprintf(text,sizeof text,"Volume  %u%%",current_volume);
    lv_label_set_text(control_label,text);
}
static void select_parameter(unsigned index)
{
    if (index>=rnbo_patch_layout.parameter_count || !actions.parameter || !actions.parameter_value) return;
    selected=index;patch_view_select(index);
    lv_slider_set_range(control_slider,0,1000);lv_obj_clear_flag(volume_button,LV_OBJ_FLAG_HIDDEN);control_text();
}
static void show_volume(lv_event_t *event)
{
    (void)event;selected=PATCH_NO_PARAMETER;patch_view_select(selected);
    lv_slider_set_range(control_slider,0,100);lv_slider_set_value(control_slider,current_volume,LV_ANIM_OFF);
    lv_obj_add_flag(volume_button,LV_OBJ_FLAG_HIDDEN);control_text();
}
static void panic_pressed(lv_event_t *event)
{
    (void)event;actions.panic();lv_label_set_text(status_label,"Muted");
}
static void resume_pressed(lv_event_t *event){(void)event;actions.resume();}
static void value_changed(lv_event_t *event)
{
    (void)event;unsigned value=(unsigned)lv_slider_get_value(control_slider);
    bool accepted;
    if (selected<rnbo_patch_layout.parameter_count && actions.parameter)
        accepted=actions.parameter(selected,(float)value/1000);
    else {current_volume=value;accepted=actions.volume(value);}
    if (!accepted) lv_label_set_text(status_label,"Resume to edit / queue busy");
    control_text();
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
esp_err_t board_display_start(const board_display_actions *callbacks)
{
    if (!callbacks || !callbacks->panic || !callbacks->resume || !callbacks->volume || !callbacks->source_label)
        return ESP_ERR_INVALID_ARG;
    actions=*callbacks;current_volume=callbacks->initial_volume;
    esp_err_t result=touch_display_start();if (result!=ESP_OK) return result;
    if (!bsp_display_lock(2000)) return ESP_ERR_TIMEOUT;
    lv_obj_t *screen=lv_scr_act();
    lv_obj_set_style_bg_color(screen,lv_color_black(),0);lv_obj_clear_flag(screen,LV_OBJ_FLAG_SCROLLABLE);
    label(screen,rnbo_patch_layout.title,16,12,250,&rnbo_barlow_22);
    battery_label=label(screen,"USB",286,18,66,&rnbo_barlow_14);
    status_label=label(screen,"Starting",16,40,120,&rnbo_barlow_14);
    label(screen,"RNBO / MAIN",238,40,114,&rnbo_barlow_14);
    patch_view_create(screen,select_parameter);
    render_label=label(screen,"CPU --",16,303,336,&rnbo_barlow_14);
    control_label=label(screen,"Volume  100%",16,332,260,&rnbo_barlow_16);
    volume_button=button(screen,"Volume",284,328,68,29,show_volume);lv_obj_add_flag(volume_button,LV_OBJ_FLAG_HIDDEN);
    control_slider=lv_slider_create(screen);lv_obj_set_pos(control_slider,24,372);lv_obj_set_size(control_slider,320,4);
    lv_obj_set_style_bg_color(control_slider,lv_color_hex(0x404040),LV_PART_MAIN);
    lv_obj_set_style_bg_color(control_slider,lv_color_white(),LV_PART_INDICATOR);
    lv_obj_set_style_bg_color(control_slider,lv_color_white(),LV_PART_KNOB);
    lv_obj_set_style_pad_all(control_slider,8,LV_PART_KNOB);
    lv_slider_set_range(control_slider,0,100);lv_slider_set_value(control_slider,(int)current_volume,LV_ANIM_OFF);
    lv_obj_add_event_cb(control_slider,value_changed,LV_EVENT_VALUE_CHANGED,NULL);
    button(screen,"Resume",16,402,158,34,resume_pressed);button(screen,"Panic",194,402,158,34,panic_pressed);
    control_text();ready=true;bsp_display_unlock();return bsp_display_brightness_set(55);
}
void board_display_update(bool muted,bool fault,unsigned volume,uint32_t render_us,uint32_t peak_us)
{
    if (!ready) return;
    touch_battery battery={.percent=-1};esp_err_t battery_result=touch_display_battery(&battery);
    if (!bsp_display_lock(20)) return;
    lv_label_set_text(status_label,fault?"Audio fault / muted":muted?"Muted":"Playing");
    lv_obj_set_style_text_color(status_label,lv_color_hex(fault?0xff6060:0xffffff),0);
    char text[96];unsigned current=(unsigned)(((uint64_t)render_us*44100u)/(256u*1000u));
    unsigned peak=(unsigned)(((uint64_t)peak_us*44100u)/(256u*1000u));
    snprintf(text,sizeof text,"CPU %u.%u%%      Peak %u.%u%%      44.1 kHz",current/10,current%10,peak/10,peak%10);
    lv_label_set_text(render_label,text);current_volume=volume;
    if (selected==PATCH_NO_PARAMETER && !lv_obj_has_state(control_slider,LV_STATE_PRESSED))
        lv_slider_set_value(control_slider,(int)volume,LV_ANIM_OFF);
    control_text();
    if (battery_result!=ESP_OK) snprintf(text,sizeof text,"Power --");
    else if (battery.present && battery.percent>=0) snprintf(text,sizeof text,"%d%%%s",battery.percent,battery.charging?" +":"");
    else snprintf(text,sizeof text,battery.usb?"USB":"Battery");
    lv_label_set_text(battery_label,text);bsp_display_unlock();
}
