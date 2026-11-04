# SPDX-License-Identifier: MIT
"""Guard the actual sys_evt callback's tiny call closure and mailbox ordering."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'firmware/components/player_network/player_network.c'


def callback_source():
    source = SOURCE.read_text()
    start = source.index('static void wifi_event(')
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        if source[end] == '{':
            depth += 1
        elif source[end] == '}':
            depth -= 1
        end += 1
    return source[start:end]


class PlayerNetworkEventTests(unittest.TestCase):
    def test_callback_has_no_formatting_socket_heap_or_regular_mutex_call(self):
        body = callback_source().split('{', 1)[1]
        calls = set(re.findall(r'\b([A-Za-z_]\w*)\s*\(', body)) - {'if', 'sizeof'}
        self.assertEqual(calls, {'portENTER_CRITICAL', 'portEXIT_CRITICAL'})

    def test_actual_callback_scalar_mailbox_keeps_latest_link_event(self):
        compiler = shutil.which('cc')
        if not compiler:
            self.skipTest('A host C compiler is required')
        source = SOURCE.read_text()
        mailbox = re.search(r'static struct \{[^}]+\} wifi_events;', source).group(0)
        prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
typedef const void *esp_event_base_t;
static int wifi_tag,ip_tag,event_mux,critical_depth;
#define WIFI_EVENT (&wifi_tag)
#define IP_EVENT (&ip_tag)
enum {WIFI_EVENT_STA_START=1,WIFI_EVENT_STA_STOP=2,WIFI_EVENT_STA_DISCONNECTED=3,IP_EVENT_STA_GOT_IP=4};
typedef struct {unsigned reason;} wifi_event_sta_disconnected_t;
typedef struct {struct {struct {uint32_t addr;}ip;}ip_info;} ip_event_got_ip_t;
#define portENTER_CRITICAL(p) do {assert((p)==&event_mux);assert(critical_depth==0);++critical_depth;}while(0)
#define portEXIT_CRITICAL(p) do {assert((p)==&event_mux);assert(critical_depth==1);--critical_depth;}while(0)
'''
        cases = r'''
int main(void){
    wifi_event_sta_disconnected_t lost={.reason=205};
    ip_event_got_ip_t address={.ip_info.ip.addr=0x01020304};
    wifi_event(NULL,WIFI_EVENT,WIFI_EVENT_STA_START,NULL);
    assert(wifi_events.station_changed&&wifi_events.station_running&&!wifi_events.link_changed);
    wifi_event(NULL,WIFI_EVENT,WIFI_EVENT_STA_DISCONNECTED,&lost);
    assert(wifi_events.link_changed&&!wifi_events.link_up&&wifi_events.reason==205);
    wifi_event(NULL,IP_EVENT,IP_EVENT_STA_GOT_IP,&address);
    assert(wifi_events.link_up&&wifi_events.ip==0x01020304&&wifi_events.reason==0);
    wifi_event(NULL,WIFI_EVENT,WIFI_EVENT_STA_DISCONNECTED,&lost);
    assert(!wifi_events.link_up&&wifi_events.reason==205); /* newest wins */
    wifi_event(NULL,WIFI_EVENT,WIFI_EVENT_STA_STOP,NULL);
    assert(!wifi_events.station_running&&!wifi_events.link_up&&wifi_events.reason==0);
    wifi_event(NULL,IP_EVENT,IP_EVENT_STA_GOT_IP,NULL);
    assert(!wifi_events.link_up); /* missing event data ignored */
    assert(critical_depth==0);return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='rnbo-event-callback-') as directory:
            directory = Path(directory)
            test_source = directory / 'event.c'
            test_source.write_text('#include <stddef.h>\n' + prefix + mailbox + '\n' + callback_source() + '\n' + cases)
            executable = directory / 'event'
            result = subprocess.run([compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                                     '-fsanitize=undefined', '-fno-sanitize-recover=all', str(test_source),
                                     '-o', str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
