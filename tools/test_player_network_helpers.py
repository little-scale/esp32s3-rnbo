# SPDX-License-Identifier: MIT
"""Compile actual scan filtering and request handoff helpers; no Wi-Fi/device."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'firmware/components/player_network'


def ap(ssid, rssi=-50, channel=6, auth=3):
    if isinstance(ssid, str):
        ssid = ssid.encode()
    return {'ssid_hex': ssid.hex(), 'rssi': rssi, 'channel': channel, 'auth': auth}


class PlayerNetworkHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which('cc')
        cjson = Path(os.environ.get('IDF_PATH', str(Path.home() / 'esp/esp-idf'))) / 'components/json/cJSON'
        if not cc or not (cjson / 'cJSON.c').is_file():
            raise unittest.SkipTest('Host C compiler and installed ESP-IDF real cJSON source required')
        cls.temporary = tempfile.TemporaryDirectory(prefix='rnbo-network-helpers-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        (cls.directory / 'esp_err.h').write_text('#pragma once\ntypedef int esp_err_t;\n')
        (cls.directory / 'esp_wifi.h').write_text('''#pragma once
#include <stdint.h>
typedef enum {WIFI_AUTH_OPEN,WIFI_AUTH_WEP,WIFI_AUTH_WPA_PSK,WIFI_AUTH_WPA2_PSK,
WIFI_AUTH_WPA_WPA2_PSK,WIFI_AUTH_ENTERPRISE,WIFI_AUTH_WPA3_PSK,WIFI_AUTH_WPA2_WPA3_PSK,
WIFI_AUTH_WAPI_PSK,WIFI_AUTH_OWE,WIFI_AUTH_WPA3_ENT_192,WIFI_AUTH_WPA3_EXT_PSK,
WIFI_AUTH_WPA3_EXT_PSK_MIXED_MODE,WIFI_AUTH_DPP,WIFI_AUTH_WPA3_ENTERPRISE,
WIFI_AUTH_WPA2_WPA3_ENTERPRISE,WIFI_AUTH_WPA_ENTERPRISE} wifi_auth_mode_t;
typedef struct {uint8_t ssid[33];uint8_t primary;int8_t rssi;wifi_auth_mode_t authmode;} wifi_ap_record_t;
''')
        (cls.directory / 'driver.c').write_text(r'''
#include "player_network_scan.h"
#include "player_network_handoff.h"
#include "cJSON.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int handoff(void){
    player_network_handoff slot={0};char command[8192];
    strcpy(slot.command,"player-info");assert(player_handoff_publish(&slot,7));
    assert(!player_handoff_poll(&slot,command,3)&&!slot.delivered);
    assert(player_handoff_poll(&slot,command,sizeof(command))==7&&!strcmp(command,"player-info"));
    assert(!player_handoff_poll(&slot,command,sizeof(command)));
    player_handoff_abandon(&slot);assert(slot.pending&&slot.delivered&&slot.abandoned);
    assert(!player_handoff_publish(&slot,8));
    assert(!player_handoff_reply(&slot,"{\"stale\":true}")&&!slot.pending);
    strcpy(slot.command,"player-volume 50");assert(player_handoff_publish(&slot,8));
    assert(player_handoff_poll(&slot,command,sizeof(command))==8);
    assert(player_handoff_reply(&slot,"{\"ok\":true}"));
    assert(!player_handoff_reply(&slot,"{\"duplicate\":true}"));
    assert(!strcmp(slot.response,"{\"ok\":true}"));
    player_handoff_abandon(&slot);assert(!slot.pending); /* already replied */
    assert(player_handoff_publish(&slot,9));player_handoff_abandon(&slot);assert(!slot.pending); /* not claimed */
    assert(player_handoff_publish(&slot,10));assert(player_handoff_poll(&slot,command,sizeof(command))==10);
    assert(!player_handoff_reply(&slot,NULL)&&!slot.pending); /* owner fallback */
    char response[PLAYER_NETWORK_RESPONSE_BYTES+2];memset(response,'x',sizeof(response));
    assert(player_handoff_publish(&slot,11));assert(player_handoff_poll(&slot,command,sizeof(command))==11);
    response[PLAYER_NETWORK_RESPONSE_BYTES]=0;assert(player_handoff_reply(&slot,response));
    assert(strlen(slot.response)==PLAYER_NETWORK_RESPONSE_BYTES);player_handoff_abandon(&slot);
    assert(player_handoff_publish(&slot,12));assert(player_handoff_poll(&slot,command,sizeof(command))==12);
    response[PLAYER_NETWORK_RESPONSE_BYTES]='x';response[PLAYER_NETWORK_RESPONSE_BYTES+1]=0;
    assert(!player_handoff_reply(&slot,response)&&!slot.pending);
    puts("handoff-pass");return 0;
}
int main(int argc,char **argv){
    if(argc==2&&!strcmp(argv[1],"handoff"))return handoff();
    assert(argc==2);cJSON *input=cJSON_Parse(argv[1]);assert(cJSON_IsArray(input));
    int count=cJSON_GetArraySize(input);assert(count<=25);wifi_ap_record_t rows[25]={0};
    for(int i=0;i<count;++i){cJSON *p=cJSON_GetArrayItem(input,i);const char *hex=cJSON_GetObjectItem(p,"ssid_hex")->valuestring;
        size_t n=strlen(hex)/2;assert(n<=33);for(size_t j=0;j<n;++j){unsigned byte;assert(sscanf(hex+2*j,"%2x",&byte)==1);rows[i].ssid[j]=(uint8_t)byte;}
        rows[i].rssi=(int8_t)cJSON_GetObjectItem(p,"rssi")->valueint;
        rows[i].primary=(uint8_t)cJSON_GetObjectItem(p,"channel")->valueint;
        rows[i].authmode=(wifi_auth_mode_t)cJSON_GetObjectItem(p,"auth")->valueint;
    }
    cJSON *result=cJSON_CreateObject();bool ok=player_wifi_scan_results(result,rows,(size_t)count);
    if(ok){char *text=cJSON_PrintUnformatted(result);assert(text);puts(text);cJSON_free(text);}
    cJSON_Delete(result);cJSON_Delete(input);return ok?0:2;
}
''')
        cls.executable = cls.directory / 'network-helpers'
        command = [cc, '-std=c11', '-D_POSIX_C_SOURCE=200809L', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-fsanitize=undefined', '-fno-sanitize-recover=all', '-I', str(cls.directory),
                   '-I', str(COMPONENT), '-I', str(COMPONENT / 'include'), '-I', str(cjson),
                   str(COMPONENT / 'player_network_scan.c'), str(COMPONENT / 'player_network_handoff.c'),
                   str(cjson / 'cJSON.c'), str(cls.directory / 'driver.c'), '-lm', '-o', str(cls.executable)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def results(self, rows, valid=True):
        result = subprocess.run([str(self.executable), json.dumps(rows)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0 if valid else 2, result.stdout + result.stderr)
        return json.loads(result.stdout)['networks'] if valid else None

    def test_scan_sorted_deduplicated_utf8_personal_and_open_only(self):
        rows = self.results([ap('Home', -80), ap('Open café', -50, auth=0), ap('Home', -25),
                             ap('<network & name>', -40), ap('enterprise', -10, auth=5),
                             ap('WEP', -10, auth=1), ap('WAPI', -10, auth=8), ap('OWE', -10, auth=9)])
        self.assertEqual(rows, [
            {'ssid': 'Home', 'rssi': -25, 'channel': 6, 'secure': True},
            {'ssid': '<network & name>', 'rssi': -40, 'channel': 6, 'secure': True},
            {'ssid': 'Open café', 'rssi': -50, 'channel': 6, 'secure': False},
        ])
        self.assertTrue(all(set(row) == {'ssid', 'rssi', 'channel', 'secure'} for row in rows))

    def test_hidden_controls_nul_suffix_and_unrepresentable_utf8_skip(self):
        invalid = [b'', b'a\0b', b'tab\t', b'line\n', b'\x7f', b'\xff', b'\xc0\x80', b'\xed\xa0\x80',
                   b'\xf4\x90\x80\x80', b'\xe2\x82', '\u0085'.encode(), b'x' * 33]
        rows = self.results([ap(value) for value in invalid] + [ap('x' * 32), ap('bad-channel', channel=0)])
        self.assertEqual([row['ssid'] for row in rows], ['x' * 32])

    def test_scan_bound_and_driver_rssi_clamping(self):
        rows = self.results([ap(f'network-{i}', -100 + i) for i in range(24)])
        self.assertEqual(len(rows), 24)
        self.assertEqual(rows[0]['ssid'], 'network-23')
        self.results([ap(str(i)) for i in range(25)], valid=False)
        rows = self.results([ap('Strong', 5), ap('Weak', -128), ap('bad-channel', channel=15)])
        self.assertEqual([row['rssi'] for row in rows], [0, -127])

    def test_actual_handoff_claim_timeout_late_reply_and_new_session(self):
        result = subprocess.run([str(self.executable), 'handoff'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), 'handoff-pass')


if __name__ == '__main__':
    unittest.main()
