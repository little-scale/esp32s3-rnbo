# SPDX-License-Identifier: MIT
"""Actual C framing/HMAC tests with independent stdlib MACs; no sockets/devices."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'firmware/components/player_network'
KEY = bytes(range(32))
SERVER = 'ab' * 32
CLIENT = 'cd' * 32


def mac(purpose, text=None, sequence=1, server=SERVER, client=CLIENT):
    message = f'RNBO-WIFI1 {purpose} {server} {client}'
    if text is not None:
        message += f' {sequence} {text}'
    return hmac.new(KEY, message.encode(), hashlib.sha256).hexdigest()


class PlayerNetworkProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which('cc')
        cjson = Path(os.environ.get('IDF_PATH', str(Path.home() / 'esp/esp-idf'))) / 'components/json/cJSON'
        if not cc or not (cjson / 'cJSON.c').is_file():
            raise unittest.SkipTest('Host C compiler and installed ESP-IDF real cJSON source required')
        cls.temporary = tempfile.TemporaryDirectory(prefix='rnbo-wifi-protocol-')
        cls.addClassCleanup(cls.temporary.cleanup)
        base = Path(cls.temporary.name)
        (base / 'mbedtls').mkdir()
        (base / 'mbedtls/md.h').write_text(r'''
#pragma once
#include <stddef.h>
#include <stdint.h>
#define MBEDTLS_MD_SHA256 1
typedef int mbedtls_md_info_t;
static inline const mbedtls_md_info_t *mbedtls_md_info_from_type(int t){static int i;return t==1?&i:NULL;}
#ifdef __APPLE__
#include <CommonCrypto/CommonHMAC.h>
typedef struct {CCHmacContext ctx;} mbedtls_md_context_t;
static inline void mbedtls_md_init(mbedtls_md_context_t *c){(void)c;}
static inline int mbedtls_md_setup(mbedtls_md_context_t *c,const mbedtls_md_info_t *i,int h){(void)c;(void)i;(void)h;return 0;}
static inline int mbedtls_md_hmac_starts(mbedtls_md_context_t *c,const unsigned char *k,size_t n){CCHmacInit(&c->ctx,kCCHmacAlgSHA256,k,n);return 0;}
static inline int mbedtls_md_hmac_update(mbedtls_md_context_t *c,const unsigned char *p,size_t n){CCHmacUpdate(&c->ctx,p,n);return 0;}
static inline int mbedtls_md_hmac_finish(mbedtls_md_context_t *c,unsigned char *out){CCHmacFinal(&c->ctx,out);return 0;}
static inline void mbedtls_md_free(mbedtls_md_context_t *c){(void)c;}
#else
#include <openssl/hmac.h>
typedef struct {HMAC_CTX *ctx;} mbedtls_md_context_t;
static inline void mbedtls_md_init(mbedtls_md_context_t *c){c->ctx=NULL;}
static inline int mbedtls_md_setup(mbedtls_md_context_t *c,const mbedtls_md_info_t *i,int h){(void)i;(void)h;c->ctx=HMAC_CTX_new();return c->ctx?0:-1;}
static inline int mbedtls_md_hmac_starts(mbedtls_md_context_t *c,const unsigned char *k,size_t n){return HMAC_Init_ex(c->ctx,k,(int)n,EVP_sha256(),NULL)?0:-1;}
static inline int mbedtls_md_hmac_update(mbedtls_md_context_t *c,const unsigned char *p,size_t n){return HMAC_Update(c->ctx,p,n)?0:-1;}
static inline int mbedtls_md_hmac_finish(mbedtls_md_context_t *c,unsigned char *out){unsigned n=0;return HMAC_Final(c->ctx,out,&n)&&n==32?0:-1;}
static inline void mbedtls_md_free(mbedtls_md_context_t *c){HMAC_CTX_free(c->ctx);}
#endif
''')
        (base / 'driver.c').write_text(r'''
#include "player_network_protocol.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
int main(int argc,char **argv){
    if(argc!=7)return 3;
    uint8_t key[32];for(unsigned i=0;i<32;++i)key[i]=(uint8_t)i;
    char command[8192],client[65],wire[PLAYER_WIFI_RESPONSE_WIRE_BYTES];
    bool ok=false;
    if(!strcmp(argv[1],"auth")){ok=player_wifi_authenticate(key,argv[2],argv[6],strlen(argv[6]),client);if(ok)puts(client);}
    else if(!strcmp(argv[1],"request")){ok=player_wifi_request(key,argv[2],argv[3],strtoull(argv[4],NULL,10),argv[6],strlen(argv[6]),command,(size_t)strtoul(argv[5],NULL,10));if(ok)puts(command);}
    else if(!strcmp(argv[1],"response")){ok=player_wifi_response(key,argv[2],argv[3],strtoull(argv[4],NULL,10),argv[6],wire,(size_t)strtoul(argv[5],NULL,10));if(ok)fputs(wire,stdout);}
    return ok?0:2;
}
''')
        cls.executable = base / 'protocol-test'
        command = [cc, '-std=c11', '-D_POSIX_C_SOURCE=200809L', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-Wno-deprecated-declarations', '-fsanitize=undefined', '-fno-sanitize-recover=all',
                   '-I', str(base), '-I', str(cjson), '-I', str(COMPONENT),
                   str(COMPONENT / 'player_network_protocol.c'), str(cjson / 'cJSON.c'),
                   str(base / 'driver.c'), '-o', str(cls.executable), '-lm']
        if sys.platform != 'darwin':
            command += ['-lcrypto']
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def run_c(self, operation, packet, *, sequence=1, capacity=8192, server=SERVER, client=CLIENT, valid=True):
        result = subprocess.run([str(self.executable), operation, server, client, str(sequence), str(capacity), packet],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0 if valid else 2, result.stdout + result.stderr)
        return result.stdout.rstrip('\n')

    def request(self, command, sequence=1, **extra):
        return json.dumps({'seq': sequence, 'command': command, 'mac': mac('REQUEST', command, sequence), **extra})

    def test_auth_binds_both_fresh_nonces_and_rejects_ambiguous_fields(self):
        auth = {'client_nonce': CLIENT, 'auth': mac('AUTH')}
        self.assertEqual(self.run_c('auth', json.dumps(auth)), CLIENT)
        for changed in ({**auth, 'client_nonce': 'ef' * 32}, {**auth, 'auth': '0' * 64},
                        {**auth, 'auth': auth['auth'].upper()}, {**auth, 'extra': 1},
                        {'auth': auth['auth']}, {'client_nonce': CLIENT, 'auth': True}):
            self.run_c('auth', json.dumps(changed), valid=False)
        self.run_c('auth', json.dumps(auth), server='01' * 32, valid=False)
        duplicate = json.dumps(auth)[:-1] + ',"auth":"' + auth['auth'] + '"}'
        self.run_c('auth', duplicate, valid=False)

    def test_exact_command_mac_sequence_and_session_separation(self):
        command = 'player-param 1 25 0 0.5'
        self.assertEqual(self.run_c('request', self.request(command)), command)
        for expected in (0, 2, 9007199254740992):
            self.run_c('request', self.request(command), sequence=expected, valid=False)
        self.run_c('request', self.request(command), client='ef' * 32, valid=False)
        self.run_c('request', self.request(command), server='12' * 32, valid=False)
        self.run_c('request', self.request(command, mac=mac('RESPONSE', command)), valid=False)
        self.run_c('request', self.request(command, extra=True), valid=False)
        for seq in ('true', '1.0', '1e0', '-1'):
            raw = self.request(command).replace('"seq": 1', '"seq": ' + seq)
            self.run_c('request', raw, valid=False)

    def test_command_length_ascii_escaping_and_full_json_framing(self):
        for command in ('player-info', 'player-test "quoted" \\ slash', 'x' * 8191):
            self.assertEqual(self.run_c('request', self.request(command)), command)
        for command in ('', 'x' * 8192, 'player-info\nplayer-pause', 'test\x00hidden', 'café'):
            self.run_c('request', self.request(command), valid=False)
        raw = self.request('player-info')
        for changed in (raw + '{}', raw[:-1], '[]', raw.replace('"seq": 1', '"seq":1,"seq":1')):
            self.run_c('request', changed, valid=False)
        self.run_c('request', raw, capacity=len('player-info'), valid=False)

    def test_response_keeps_exact_json_bytes_and_direction_domain(self):
        response = '{"name":"Café","quote":"\\\"","ok":true}\n'
        wire = self.run_c('response', response, sequence=7, capacity=6 * 16384 + 512)
        packet = json.loads(wire)
        self.assertEqual(packet['seq'], 7)
        self.assertEqual(packet['response'], response)
        self.assertEqual(packet['mac'], mac('RESPONSE', response, 7))
        self.assertNotEqual(packet['mac'], mac('REQUEST', response, 7))
        self.run_c('response', response, capacity=20, valid=False)
        self.run_c('response', 'x' * 16385, capacity=6 * 16384 + 512, valid=False)


if __name__ == '__main__':
    unittest.main()
