/* SPDX-License-Identifier: MIT */
/* Render the actual firmware widgets with the same pinned LVGL; BSP is mocked. */
#include "board_display.h"
#include "patch_layout.h"
#include "patch_view.h"
#include "touch_display.h"
#include "preview_parameters.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static lv_color_t framebuffer[368*448],buffer[368*20];
static lv_disp_draw_buf_t drawing;
static unsigned volume=28,panic_count,resume_count,parameter_calls,last_parameter;
static bool pressed;
static lv_point_t position;
static void flush(lv_disp_drv_t *driver,const lv_area_t *area,lv_color_t *colors)
{
    for(int y=area->y1;y<=area->y2;++y)for(int x=area->x1;x<=area->x2;++x)
        framebuffer[y*368+x]=*colors++;
    lv_disp_flush_ready(driver);
}
static void read_input(lv_indev_drv_t *driver,lv_indev_data_t *data)
{
    (void)driver;data->point=position;data->state=pressed?LV_INDEV_STATE_PRESSED:LV_INDEV_STATE_RELEASED;
}
esp_err_t touch_display_start(void)
{
    lv_init();lv_disp_draw_buf_init(&drawing,buffer,NULL,368*20);
    static lv_disp_drv_t driver;lv_disp_drv_init(&driver);
    driver.hor_res=368;driver.ver_res=448;driver.draw_buf=&drawing;driver.flush_cb=flush;lv_disp_drv_register(&driver);
    static lv_indev_drv_t input;lv_indev_drv_init(&input);input.type=LV_INDEV_TYPE_POINTER;input.read_cb=read_input;lv_indev_drv_register(&input);
    return ESP_OK;
}
esp_err_t touch_display_battery(touch_battery *sample){*sample=(touch_battery){.usb=true,.percent=-1};return ESP_OK;}
bool bsp_display_lock(unsigned timeout){(void)timeout;return true;}
void bsp_display_unlock(void){}
esp_err_t bsp_display_brightness_set(unsigned value){(void)value;return ESP_OK;}
static void panic(void){++panic_count;}
static void resume(void){++resume_count;}
static bool set_volume(unsigned value){volume=value;return true;}
static bool parameter(unsigned i,float v){if(i>=rnbo_patch_layout.parameter_count)return false;assert(v>=0 && v<=1);normalized_values[i]=v;++parameter_calls;last_parameter=i;return true;}
static bool value(unsigned i,float *a,float *n){if(i>=rnbo_patch_layout.parameter_count)return false;*a=actual_values[i];*n=normalized_values[i];return true;}
static void click(int x,int y)
{
    position=(lv_point_t){x,y};pressed=true;for(unsigned i=0;i<4;++i){lv_tick_inc(40);lv_timer_handler();}
    pressed=false;for(unsigned i=0;i<4;++i){lv_tick_inc(40);lv_timer_handler();}
}
static void image(const char *directory,const char *name)
{
    lv_refr_now(NULL);char path[4096];snprintf(path,sizeof path,"%s/%s.rgb",directory,name);
    FILE *out=fopen(path,"wb");assert(out);
    for(unsigned i=0;i<368*448;++i){lv_color32_t c; c.full=lv_color_to32(framebuffer[i]);unsigned char rgb[3]={c.ch.red,c.ch.green,c.ch.blue};assert(fwrite(rgb,1,3,out)==3);}
    fclose(out);
}
int main(int argc,char **argv)
{
    assert(argc==2);board_display_actions actions={.panic=panic,.resume=resume,.volume=set_volume,.parameter=parameter,.parameter_value=value,.initial_volume=28,.source_label="Preview"};
    assert(board_display_start(&actions)==ESP_OK);board_display_update(false,false,28,250,521);image(argv[1],"patch");
    for(unsigned i=0;i<rnbo_patch_layout.node_count;++i){const patch_node *n=&rnbo_patch_layout.nodes[i];if(n->parameter!=PATCH_NO_PARAMETER){click(16+n->x+n->width/2,64+n->y+n->height/2);image(argv[1],"parameter");click(336,374);assert(parameter_calls>0 && last_parameter==n->parameter && normalized_values[last_parameter]>0.95f);click(318,342);click(180,374);assert(volume>40 && volume<60);break;}}
    click(274,419);assert(panic_count==1);board_display_update(true,false,28,250,521);image(argv[1],"panic");
    click(95,419);assert(resume_count==1);
    lv_mem_monitor_t mem;lv_mem_monitor(&mem);assert(lv_mem_test()==LV_RES_OK);
    printf("{\"panic\":%u,\"resume\":%u,\"parameter_slider_events\":%u,\"lvgl_free\":%u,\"lvgl_largest\":%u}\n",panic_count,resume_count,parameter_calls,(unsigned)mem.free_size,(unsigned)mem.free_biggest_size);
    return 0;
}
