"""Computer-only actual XIAO adapter clocks/PCM/capture regression at both rates."""
from pathlib import Path
import tempfile,subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
class AdapterTests(unittest.TestCase):
    def test_i2s_clock_pcm_capture_boundaries_and_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            (folder/'driver').mkdir()
            for header in ('driver/i2s_std.h','driver/gpio.h','esp_err.h','esp_check.h','esp_heap_caps.h','esp_random.h'):
                (folder/header).write_text('#include "fake_idf.h"\n')
            (folder/'fake_idf.h').write_text((ROOT/'tests/xiao_i2s_fake.h').read_text())
            for rate in (44100,16000):
                with self.subTest(rate=rate):
                    (folder/'sdkconfig.h').write_text('#define CONFIG_RNBO_S3_HEADLESS 1\n'
                        '#define CONFIG_RNBO_S3_I2S_BCLK 7\n#define CONFIG_RNBO_S3_I2S_WS 8\n#define CONFIG_RNBO_S3_I2S_DOUT 9\n'
                        + '')
                    binary=folder/'test'
                    subprocess.run(['cc','-std=c11','-O1','-Wall','-Wextra','-Werror',
                        '-fsanitize=undefined,bounds','-fno-sanitize-recover=all','-I'+str(folder),f'-DRNBO_S3_SAMPLE_RATE={rate}',
                        '-I'+str(ROOT/'firmware/components/board_audio/include'),
                        str(ROOT/'tests/xiao_i2s_test.c'),'-o',str(binary)],check=True,capture_output=True)
                    subprocess.run([str(binary),str(rate)],check=True,capture_output=True)


if __name__=="__main__":unittest.main(verbosity=2)
