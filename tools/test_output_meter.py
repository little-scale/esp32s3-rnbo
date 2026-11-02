# SPDX-License-Identifier: MIT
"""Verify the meter follows final PCM, including gain ramp, mute and routing."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class OutputMeterTests(unittest.TestCase):
    def test_final_pcm_level_tracks_gain_mute_clipping_and_mono_cancellation(self):
        compiler=shutil.which('cc')
        if not compiler:self.skipTest('C compiler required')
        source=r'''
#include "pcm_output.h"
#include "output_meter.h"
#include <assert.h>
#include <math.h>
#include <string.h>
static float left[256],right[256];
static int16_t pcm[512];
static uint32_t render(pcm_output *s,unsigned volume,unsigned channels,int mute) {
    for(unsigned i=0;i<5;++i)assert(pcm_output_render(s,left,right,pcm,256,channels,volume,.5f,mute));
    return output_meter_peak_q15(pcm,256*channels);
}
int main(void) {
    pcm_output s;pcm_output_init(&s);
    for(unsigned i=0;i<256;++i)left[i]=right[i]=1;
    uint32_t full=render(&s,100,1,0);assert(full==16384);
    uint32_t quarter=render(&s,25,1,0);assert(quarter==4096 && quarter*4==full);
    assert(render(&s,0,1,0)==0);
    assert(render(&s,100,1,1)==0);
    for(unsigned i=0;i<256;++i)right[i]=-left[i];
    assert(render(&s,100,1,0)==0); /* Final mono mix, not separate L/R peaks. */
    assert(render(&s,100,2,0)==16384);
    for(unsigned i=0;i<256;++i)left[i]=right[i]=8;
    assert(render(&s,100,1,0)==32767); /* Post-saturation, not an overrange float. */
    for(unsigned i=0;i<256;++i)left[i]=right[i]=NAN;
    assert(render(&s,100,1,0)==0);
    const int16_t edges[]={0,-32768,32767,-1};
    int16_t original[4];memcpy(original,edges,sizeof edges);
    assert(output_meter_peak_q15(edges,4)==32768);
    assert(!memcmp(edges,original,sizeof edges));
    assert(output_meter_peak_q15(0,8)==0 && output_meter_peak_q15(edges,0)==0);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'meter.c').write_text(source)
            command=[compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror','-fno-fast-math',
                     '-fsanitize=undefined','-fno-sanitize-recover=all',
                     '-I'+str(ROOT/'firmware/components/pcm_output/include'),str(p/'meter.c'),
                     str(ROOT/'firmware/components/pcm_output/pcm_output.c'),'-lm','-o',str(p/'meter')]
            built=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(built.returncode,0,built.stderr)
            ran=subprocess.run([str(p/'meter')],capture_output=True,text=True)
            self.assertEqual(ran.returncode,0,ran.stderr)


if __name__=='__main__':unittest.main()
