# SPDX-License-Identifier: MIT
"""Local Float32-store identity for the generated onepole clamp statement.

This changes neither coefficient evaluation nor the recurrence. The proof is
local: the operand and stored value must be an ordinary binary32 float. Every
replacement remains one compound statement, including in unbraced control flow.
"""
import hashlib
import re

CONTRACT = '''/* RNBO onepole Float32 clamp: fixed nearest/even value equivalence only. */
#include <float.h>
#include <limits>
#include <type_traits>
#if defined(__FAST_MATH__) || (defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__ > 0)
#error "Float32 onepole clamp requires strict floating-point compilation"
#endif
#if FLT_RADIX != 2 || FLT_MANT_DIG != 24 || FLT_MAX_EXP != 128 || FLT_MIN_EXP != -125 || FLT_EVAL_METHOD != 0
#error "Float32 onepole clamp requires binary32 without extended evaluation"
#endif
#if DBL_MANT_DIG != 53 || DBL_MAX_EXP != 1024 || DBL_MIN_EXP != -1021
#error "Float32 onepole clamp retains binary64 original constants and clocks"
#endif
static_assert(sizeof(float) == 4 && sizeof(double) == 8 &&
              ::std::numeric_limits<float>::is_iec559 &&
              ::std::numeric_limits<double>::is_iec559,
              "Float32 onepole clamp requires IEEE binary32/binary64");
'''
PATTERN = re.compile(
    r'(?m)^(?P<indent>[ \t]*)(?P<name>__onepole_tilde_[0-9]+_a0) = '
    r'\((?P=name) > 0\.99999 \? 0\.99999 : '
    r'\((?P=name) < 0\.00001 \? 0\.00001 : (?P=name)\)\);'
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def directive_ranges(text):
    """Include complete backslash-continued directives, before comment masking."""
    offset = 0
    start = None
    result = []
    for line in text.splitlines(keepends=True):
        if start is None and line.lstrip().startswith(('#', '%:')):
            start = offset
        offset += len(line)
        if start is not None and not line.rstrip('\r\n').endswith('\\'):
            result.append((start, offset))
            start = None
    if start is not None:
        result.append((start, offset))
    return result


def transform(source, *, code_mask):
    if not isinstance(source, bytes):
        raise ValueError('onepole-clamp: immutable source bytes required')
    text = source.decode()
    if CONTRACT in text:
        raise ValueError('onepole-clamp: already transformed source')
    if '\\\n' in text or '\\\r\n' in text:
        raise ValueError('onepole-clamp: line-spliced source is not admitted')
    if '??=' in text:
        raise ValueError('onepole-clamp: trigraph source is not admitted')
    masked = code_mask(text)
    if not isinstance(masked, str) or len(masked) != len(text):
        raise ValueError('onepole-clamp: invalid C++ lexical mask')
    if re.search(r'(?m)^[ \t]*(?:#|%:)[ \t]*(?:line\b|[0-9])|\b__COUNTER__\b', masked):
        raise ValueError('onepole-clamp: custom source-location/counter directives are not admitted')
    matches = list(PATTERN.finditer(masked))
    if not matches:
        raise ValueError('onepole-clamp: no exact generated clamp statement')
    directives = directive_ranges(masked)
    edits = []
    statements = []
    for match in matches:
        a, b = match.span()
        if text[a:b] != match[0] or any(a < end and b > start for start, end in directives):
            raise ValueError('onepole-clamp: directive or nonliteral statement context')
        name = match['name']
        indent = match['indent']
        statement = match[0][len(indent):]
        typed = statement.replace('0.99999', '0.99999f').replace('0.00001', '0.00001f')
        # Directives disappear before parsing; the replacement is ONE statement.
        # Macro substitution must not turn the repeated identifier into an
        # expression with hidden side effects or a different number of reads.
        original_line = text[:a].count('\n') + 1
        guards = (name, 'static_assert', 'float', 'decltype', 'std', 'is_same', 'value')
        replacement = (
            '#if ' + ' || '.join('defined(' + token + ')' for token in guards) +
            '\n#error "Float32 onepole clamp rejects macros in operand/type guards"\n#endif\n' +
            indent + '{\n' + indent + '    static_assert(::std::is_same<decltype(' + name +
            '), float>::value, "Float32 onepole clamp requires an ordinary non-volatile float");\n' +
            indent + '    ' + typed + '\n' + indent + '}' +
            '\n#line ' + str(original_line) + '\n'
        )
        edits.append((a, b, replacement))
        statements.append({'operand': name, 'original_line': text[:a].count('\n') + 1,
                           'original_statement_sha256': sha(match[0].encode()),
                           'replacement_sha256': sha(replacement.encode())})
    changed = text
    for a, b, replacement in reversed(edits):
        changed = changed[:a] + replacement + changed[b:]
    restored = changed
    for (a, b, replacement), match in zip(edits, matches):
        if restored[a:a + len(replacement)] != replacement:
            raise ValueError('onepole-clamp: full inverse differs')
        restored = restored[:a] + match[0] + restored[a + len(replacement):]
    if restored != text:
        raise ValueError('onepole-clamp: full inverse differs')
    output = (CONTRACT + '#line 1\n' + changed).encode()
    return output, {
        'name': 'rnbo-1.4.4-float32-onepole-clamp-v1', 'file': 'rnbo_source.h',
        'input_sha256': sha(source), 'prepared_sha256': sha(output),
        'contract_sha256': sha(CONTRACT.encode()), 'statement_count': len(statements),
        'statements': statements, 'full_inverse_byte_identity': True,
        'proof_scope': 'ordinary finite binary32 operand stored to itself; fixed nearest-even rounding',
        'lower_float32_bits': '3727c5ac', 'upper_float32_bits': '3f7fff58',
        'lower_predicate_only_difference': 'a0 == lowerFloat32; both stored results are lowerFloat32',
        'control_flow': 'single compound statement; no runtime local objects',
        'coefficient_and_recurrence_unchanged': True, 'state_layout_and_scheduler_unchanged': True,
        'baseline_accuracy_failures_repaired': False, 'target_cpu_gain_claimed': False,
        'floating_environment_equivalence_claimed': False, 'nan_payload_equivalence_claimed': False,
    }
