# SPDX-License-Identifier: MIT
"""Compile actual headless player control/audio code; no licensed DSP or device.

Fake DMA ACKs, loader and storage inject faults at ownership boundaries. The
actual package parser/cJSON/SHA/PCM and actual player command/audio/guard functions
run unchanged. This is a control-flow test, not a FreeRTOS scheduling or HIL proof.
"""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('control_storage_fixtures', ROOT / 'tools/test_player_store.py')
storage = importlib.util.module_from_spec(spec); spec.loader.exec_module(storage)

STUBS = {
    'sdkconfig.h': '#pragma once\n#define CONFIG_RNBO_S3_HEADLESS 1\n',
    'esp_log.h': '#pragma once\n#define ESP_LOGI(...) ((void)0)\n#define ESP_LOGE(...) ((void)0)\n',
    'esp_timer.h': '#pragma once\n#include <stdint.h>\nint64_t esp_timer_get_time(void);\n',
    'esp_app_desc.h': '#pragma once\n#include <stdint.h>\ntypedef struct {uint8_t app_elf_sha256[32];} esp_app_desc_t;\nconst esp_app_desc_t *esp_app_get_description(void);\n',
    'freertos/FreeRTOS.h': '''#pragma once
#include <stdint.h>
typedef void *TaskHandle_t;
typedef void *QueueHandle_t;
typedef struct {unsigned unused;} StaticTask_t;
typedef uint32_t StackType_t;
#define pdTRUE 1
#define pdMS_TO_TICKS(n) (n)
''',
    'freertos/task.h': '''#pragma once
#include "FreeRTOS.h"
void vTaskDelay(unsigned);
void vTaskDelete(void *);
TaskHandle_t xTaskCreateStaticPinnedToCore(void (*)(void *),const char *,unsigned,void *,unsigned,StackType_t *,StaticTask_t *,unsigned);
''',
    'freertos/queue.h': '''#pragma once
#include "FreeRTOS.h"
QueueHandle_t xQueueCreate(unsigned,unsigned);
int xQueueSend(QueueHandle_t,const void *,unsigned);
int xQueueReceive(QueueHandle_t,void *,unsigned);
int xQueuePeek(QueueHandle_t,void *,unsigned);
int xQueueReset(QueueHandle_t);
int xQueueOverwrite(QueueHandle_t,const void *);
''',
}

class PlayerControlTests(unittest.TestCase):
    def test_actual_command_transaction_audio_epoch_and_guard(self):
        compiler = shutil.which('cc')
        if not compiler:
            self.skipTest('A host C compiler is required')
        idf = Path(os.environ.get('IDF_PATH', str(Path.home() / 'esp/esp-idf')))
        cjson = idf / 'components/json/cJSON'
        if not (cjson / 'cJSON.c').is_file():
            self.skipTest('Real cJSON source is required from an installed ESP-IDF')
        with tempfile.TemporaryDirectory(prefix='rnbo-player-control-') as directory:
            out = Path(directory);includes=out/'include'
            headers = dict(storage.STUBS, **STUBS)
            headers['esp_heap_caps.h'] += '''
#define MALLOC_CAP_INTERNAL 4u
void *heap_caps_calloc(size_t,size_t,unsigned);
size_t heap_caps_get_free_size(unsigned);
'''
            headers['esp_err.h'] += '\n#include <assert.h>\n#define ESP_ERROR_CHECK(x) assert((x)==ESP_OK)\n'
            headers['nvs.h'] += '''
esp_err_t nvs_get_str(nvs_handle_t,const char *,char *,size_t *);
esp_err_t nvs_set_str(nvs_handle_t,const char *,const char *);
'''
            for name, text in headers.items():
                target=includes/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
            flags=[compiler,'-std=c11','-D_POSIX_C_SOURCE=200809L','-O1','-Wall','-Wextra','-Werror',
                   '-Wno-deprecated-declarations','-Wno-unused-function','-Wno-unused-variable',
                   '-fsanitize=undefined','-fno-sanitize-recover=all','-I',str(includes),
                   '-I',str(HERE/'loader_stubs'),'-I',str(cjson),'-I',str(ROOT/'module-sdk/include'),
                   '-I',str(ROOT/'firmware/components/player_loader/include'),
                   '-I',str(ROOT/'firmware/components/player_store/include'),
                   '-I',str(ROOT/'firmware/components/board_audio/include'),
                   '-I',str(ROOT/'firmware/components/pcm_output/include')]
            # Keep the actual parser/clear implementation, replacing only storage
            # boundaries with assertions/fault injection in control_host.c.
            names=('init','stage','commit','promote_previous','read','free')
            renamed=[f'-Dplayer_store_{name}=control_unused_store_{name}' for name in names]
            commands=[flags+renamed+['-c',str(ROOT/'firmware/components/player_store/player_store.c'),'-o',str(out/'store.o')],
                      flags+[f'-DPLAYER_MAIN_SOURCE="{ROOT / "firmware/main/player_main.c"}"',
                        str(HERE/'control_stubs/control_host.c'),str(out/'store.o'),
                        str(ROOT/'firmware/components/pcm_output/pcm_output.c'),str(cjson/'cJSON.c'),'-o',str(out/'control'),'-lm']]
            if sys.platform != 'darwin': commands[-1].append('-lcrypto')
            for command in commands:
                compiled=subprocess.run(command,capture_output=True,text=True,timeout=30)
                self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
            fixture=out/'test.rnbopkg';fixture.write_bytes(storage.package())
            result=subprocess.run([str(out/'control'),str(fixture)],capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('lifetime counters PASS',result.stdout)

if __name__=='__main__':unittest.main()
