/* SPDX-License-Identifier: MIT */
#include "average_oracle.h"
#include <math.h>
#include <stddef.h>
bool object_average_oracle_fill(const float *input,uint32_t total,uint32_t first,
    uint32_t frames,uint32_t window,uint32_t initial_available,float *output,double *rounding)
{
    if(!input||!output||!rounding||!total||total>1024u*256u||!frames||first>total||frames>total-first||
       !window||window>64||initial_available>window||!isfinite(*rounding)||*rounding<0)return false;
    for(uint32_t offset=0;offset<frames;++offset){
        uint32_t n=first+offset,start=n>=window?n-window+1u:0u;
        uint32_t available=initial_available+n+1u;if(available>window)available=window;
        for(unsigned channel=0;channel<2;++channel){
            double sum=0;
            for(uint32_t j=start;j<=n;++j){float x=input[2u*j+channel];if(!isfinite(x))return false;sum+=(double)x;}
            double mean=sum/(double)available;float rounded=(float)mean;
            if(!isfinite(mean)||!isfinite(rounded))return false;
            double error=fabs(mean-(double)rounded);if(error>*rounding)*rounding=error;
            output[2u*offset+channel]=rounded;
        }
    }
    return true;
}
