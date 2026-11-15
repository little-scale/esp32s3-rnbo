/* SPDX-License-Identifier: MIT */
#pragma once
#include "rnbo_s3_led.h"
/* Included after the genuine RNBO_Common.h. The generated INTERNALENGINE*
 * overloads still use the reviewed MinimalEngine clock/event implementation. */
static_assert(sizeof(RNBO::number)==sizeof(float),"LED payload arithmetic requires the reviewed Float32 RNBO scalar");
class RNBO_S3_LEDEngine final : public RNBO::MinimalEngine<> {
public:
    rnbo_s3_led_state leds{};
    explicit RNBO_S3_LEDEngine(RNBO::PatcherInterface *p):RNBO::MinimalEngine<>(p){}
    void sendListMessage(RNBO::MessageTag tag,RNBO::MessageTag,const RNBO::list& payload,RNBO::MillisecondTime) override {
        if(tag!=RNBO::TAG("led_rgb"))return;
        const RNBO::Index n=payload.length;
        if(n!=3&&n!=4&&n!=36){rnbo_s3_led_apply(&leds,nullptr,0);return;}
        float values[36];for(unsigned i=0;i<(unsigned)n;++i)values[i]=payload[i];
        rnbo_s3_led_apply(&leds,values,(uint32_t)n);
    }
    void sendNumMessage(RNBO::MessageTag tag,RNBO::MessageTag,RNBO::number,RNBO::MillisecondTime) override {
        if(tag==RNBO::TAG("led_rgb"))rnbo_s3_led_apply(&leds,nullptr,0);
    }
    void sendBangMessage(RNBO::MessageTag tag,RNBO::MessageTag,RNBO::MillisecondTime) override {
        if(tag==RNBO::TAG("led_rgb"))rnbo_s3_led_apply(&leds,nullptr,0);
    }
};
