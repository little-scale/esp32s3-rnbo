# SPDX-License-Identifier: MIT
"""Adversarial precision inventory checks; synthetic code is not RNBO DSP."""
import hashlib
from pathlib import Path
import struct
import unittest

from audit_precision import (Instruction, Symbol, audit_source, elf_identity,
                             parse_instructions, parse_locations, parse_symbols,
                             precision_kind, resolve_calls)


class PrecisionAuditTests(unittest.TestCase):
    def test_audio_reachability_does_not_turn_double_clocks_into_candidates(self):
        source = '''// café: void fake_perform() { double x=9.0; }
void process() { this->cycle_tilde_01_perform(); this->sampstoms(256); }
void cycle_tilde_01_perform() { this->pitch(); uint32_trunc(3.5); }
number pitch() { return 1.25; }
MillisecondTime sampstoms(number value) { return value * 0.001; }
void initialize() { this->table_init(); }
void table_init() { double value=1.0; }
number uncalled() { return 2.0; }
Float64BufferRef comb_tilde_01_feedForward_buffer;
'''
        report = audit_source(source.encode())
        methods = {m['name']: m for m in report['methods']}
        self.assertNotIn('fake_perform', methods)
        self.assertEqual(methods['pitch']['domain'], 'audio_reachable')
        self.assertEqual(methods['sampstoms']['domain'], 'shared_time_conversion_needs_review')
        self.assertTrue(methods['sampstoms']['direct_audio_graph_reachable'])
        self.assertEqual(methods['table_init']['domain'], 'setup_or_state')
        self.assertEqual(methods['uncalled']['domain'], 'unknown')
        self.assertEqual(report['rings'][0]['sample_bytes'], 8)
        self.assertEqual(methods['pitch']['method_sha256'], hashlib.sha256(b'number pitch() { return 1.25; }').hexdigest())
        self.assertEqual(len(methods['cycle_tilde_01_perform']['uint32_trunc_source_uses']), 1)

    def test_clock_typed_duration_helper_can_be_audio_work(self):
        report = audit_source(b'void process() {this->comb_tilde_01_perform();}\nvoid comb_tilde_01_perform(){this->mstosamps(1.0);}\nnumber mstosamps(MillisecondTime x){return x*44.1;}\n')
        methods = {m['name']:m for m in report['methods']}
        self.assertTrue(methods['mstosamps']['direct_audio_graph_reachable'])
        self.assertEqual(methods['mstosamps']['domain'],'shared_time_conversion_needs_review')
        self.assertTrue(methods['mstosamps']['clock_type_signature_needs_context'])

    def test_helper_categories_keep_wide_integer_separate_from_double(self):
        expected = {'__fixsfdi':'float32_int64_conversion', '__fixdfdi':'float64_conversion',
                    '__extendsfdf2':'float64_conversion', '__floatundidf':'float64_conversion',
                    '__muldf3':'float64_arithmetic', '__gtdf2':'float64_comparison',
                    '__divsf3':'float32_software_arithmetic', 'exp':'float64_math', 'expf':'float32_math'}
        for name, kind in expected.items():
            with self.subTest(name=name): self.assertEqual(precision_kind(name), kind)

    def test_zero_size_libgcc_symbols_and_nested_template_targets_are_kept(self):
        symbols = parse_symbols('00000010 00000004 W RNBO::Patch<Engine<4u> >::process()\n00000100 t __fixsfdi\n40001000 A __adddf3\n40002000 A random_integer_constant\n')
        self.assertEqual(symbols[1], Symbol(256, 0, '__fixsfdi'))
        self.assertEqual(symbols[2], Symbol(0x40001000,0,'__adddf3'))
        self.assertEqual(len(symbols),3)
        code = parse_instructions(' 10: 000005 call8 100 <RNBO::Patch<Engine<4u> >::helper()>\n 13: f01d retw.n\n')
        calls = resolve_calls(code, [Symbol(256, 0, '__fixsfdi')])
        self.assertEqual(calls[0]['target'], '__fixsfdi')

    def test_register_copy_clobber_and_overlapping_spills(self):
        instructions = [Instruction(0,'l32r','a3, 80 <pool> (100 <__fixsfdi>)'),
                        Instruction(3,'s32i','a3, a1, 48'), Instruction(6,'ssi','f0, a1, 16'),
                        Instruction(9,'l32i','a8, a1, 48'), Instruction(12,'callx8','a8'),
                        Instruction(15,'callx8','a8'), # argument/window register was killed
                        Instruction(18,'l32i','a8, a1, 48'), Instruction(21,'callx8','a8'),
                        Instruction(24,'s16i','a2, a1, 50'), # overlaps high half of spill
                        Instruction(27,'l32i','a8, a1, 48'), Instruction(30,'callx8','a8')]
        calls = resolve_calls(instructions, [Symbol(256,0,'__fixsfdi')])
        self.assertEqual([c['target'] for c in calls], ['__fixsfdi', None, None, None])
        # The second unresolved call invalidates stack facts too. A known
        # numeric call alone may retain an unrelated local function spill.
        calls = resolve_calls(instructions[:5]+instructions[6:8], [Symbol(256,0,'__fixsfdi')])
        self.assertEqual([c['target'] for c in calls], ['__fixsfdi','__fixsfdi'])

    def test_control_flow_join_never_uses_only_the_last_literal_load(self):
        code = [Instruction(0,'beqz','a2, 9 <Patch<Engine<4> >::process()+9>'),
                Instruction(3,'l32r','a8, 80 <pool> (100 <exp>)'), Instruction(6,'j','c <join>'),
                Instruction(9,'l32r','a8, 84 <pool> (200 <expf>)'), Instruction(12,'callx8','a8')]
        symbols = [Symbol(256,0,'exp'),Symbol(512,0,'expf')]
        self.assertIsNone(resolve_calls(code,symbols)[0]['target'])
        code[3] = Instruction(9,'l32r','a8, 80 <pool> (100 <exp>)')
        self.assertEqual(resolve_calls(code,symbols)[0]['target'], 'exp')

    def test_hardware_loop_and_tail_jump_are_visible(self):
        code = [Instruction(0,'l32r','a3, 80 <pool> (100 <expf>)'),Instruction(3,'loopnez','a2, c <end>'),
                Instruction(6,'callx8','a3'),Instruction(9,'nop',''),Instruction(12,'jx','a3')]
        calls = resolve_calls(code,[Symbol(256,0,'expf')])
        self.assertEqual([c['target'] for c in calls],['expf','expf'])
        self.assertTrue(calls[-1]['tail_jump'])

    def test_source_literals_and_braces_in_strings_do_not_create_methods(self):
        report = audit_source(b'const char *x=R"tag(void fake_perform(){ 1.2; })tag";\nvoid process() { const char *s="} 0.5"; }\n')
        self.assertEqual([m['name'] for m in report['methods']], ['process'])
        self.assertEqual(report['methods'][0]['unsuffixed_decimal_literals'], [])

    def test_inline_location_stack_is_not_split_at_spaces_or_template_commas(self):
        result = parse_locations('0x00000010\nRNBO::Patch<Engine<4> >::process(float*, unsigned long)\n/some path/rnbo_source.h:12 (discriminator 2)\nadvanceTime\nclock.h:9\n0x00000020\n??\n??:0\n')
        self.assertEqual(len(result[16]),2)
        self.assertEqual(result[16][0]['location'],'/some path/rnbo_source.h:12 (discriminator 2)')

    def test_malformed_or_wrong_architecture_elf_is_rejected(self):
        for value in (b'', b'\x7fELF'+bytes(48)):
            with self.assertRaises(ValueError): elf_identity(value)
        value=bytearray(52);value[:7]=b'\x7fELF\x01\x01\x01';struct.pack_into('<HH',value,16,3,62)
        with self.assertRaisesRegex(ValueError,'Xtensa'): elf_identity(bytes(value))


if __name__ == '__main__': unittest.main()
