
import unittest

from nflxprofile import flamegraph, nflxprofile_pb2


def dict_from_frame_extras(fe):
    return {
        'javascript': fe.javascript,
        'real_name': fe.real_name,
        'optimized': fe.optimized,
        'v8_jit': fe.v8_jit,
    }


class TestNodeJsStackProcessor(unittest.TestCase):

    def test_node_naming(self):
        tests = [
            {
                'input_name': 'LazyCompile:processTicksAndRejections internal/process/task_queues.js:69',
                'libtype': 'jit',
                'expected_name': 'processTicksAndRejections',
                'extras': {
                    'javascript': True,
                    'optimized': True,
                    'real_name': 'LazyCompile:processTicksAndRejections internal/process/task_queues.js:69',
                    'v8_jit': True,
                },
            },
            {
                'input_name': 'Builtins_ArgumentsAdaptorTrampoline',
                'libtype': 'user',
                'expected_name': 'Builtins_ArgumentsAdaptorTrampoline',
                'extras': {
                    'javascript': False,
                    'optimized': None,
                    'real_name': 'Builtins_ArgumentsAdaptorTrampoline',
                    'v8_jit': False,
                },
            },
            {
                'input_name': 'LazyCompile: /apps/nodequark/etc/routes/node_modules/@netflix-internal/naql-ipc/lib/ipc/AbstractClient.js:213',  # noqa: E501
                'libtype': 'jit',
                'expected_name': '(anonymous)',
                'extras': {
                    'javascript': True,
                    'optimized': True,
                    'real_name': 'LazyCompile: /apps/nodequark/etc/routes/node_modules/@netflix-internal/naql-ipc/lib/ipc/AbstractClient.js:213',  # noqa: E501
                    'v8_jit': True,
                },
            },
            {
                'input_name': 'v8::internal::LoadIC::Load',
                'libtype': 'user',
                'expected_name': 'v8::internal::LoadIC::Load',
                'extras': {
                    'javascript': False,
                    'optimized': None,
                    'real_name': 'v8::internal::LoadIC::Load',
                    'v8_jit': False,
                },
            },
            {
                'input_name': 'Builtins_CEntry_Return1_DontSaveFPRegs_ArgvOnStack_NoBuiltinExit',
                'libtype': 'user',
                'expected_name': 'Builtins_CEntry_Return1_DontSaveFPRegs_ArgvOnStack_NoBuiltinExit',
                'extras': {
                    'javascript': False,
                    'optimized': None,
                    'real_name': 'Builtins_CEntry_Return1_DontSaveFPRegs_ArgvOnStack_NoBuiltinExit',
                    'v8_jit': False,
                },
            },
            {
                'input_name': 'InterpretedFunction:parseResponse /apps/nodequark/etc/routes/node_modules/restify-clients/lib/JsonClient.js:76',  # noqa: E501
                'libtype': 'jit',
                'expected_name': 'parseResponse',
                'extras': {
                    'javascript': True,
                    'optimized': False,
                    'real_name': 'InterpretedFunction:parseResponse /apps/nodequark/etc/routes/node_modules/restify-clients/lib/JsonClient.js:76',  # noqa: E501
                    'v8_jit': True,
                },
            },
            {
                'input_name': 'node::LibuvStreamWrap::ReadStart()::{lambda(uv_stream_s*, long, uv_buf_t const*)#2}::_FUN',  # noqa: E501
                'libtype': 'user',
                'expected_name': 'node::LibuvStreamWrap::ReadStart()::{lambda(uv_stream_s*, long, uv_buf_t const*)#2}::_FUN',  # noqa: E501
                'extras': {
                    'javascript': False,
                    'optimized': None,
                    'real_name': 'node::LibuvStreamWrap::ReadStart()::{lambda(uv_stream_s*, long, uv_buf_t const*)#2}::_FUN',  # noqa: E501
                    'v8_jit': False,
                },
            },
            {
                'input_name': 'smp_call_function_single',
                'libtype': 'kernel',
                'expected_name': 'smp_call_function_single',
                'extras': {
                    'javascript': False,
                    'optimized': None,
                    'real_name': 'smp_call_function_single',
                    'v8_jit': False,
                },
            },
            {
                'input_name': 'LazyCompile:*get bar /home/nfsuper/foo.js:1',
                'libtype': 'jit',
                'expected_name': 'get bar',
                'extras': {
                    'javascript': True,
                    'optimized': True,
                    'real_name': 'LazyCompile:*get bar /home/nfsuper/foo.js:1',
                    'v8_jit': True,
                },
            },
            {
                'input_name': 'LazyCompile:get _hierarchy /apps/nodequark/etc/routes/node_modules/@netflix-internal/naql-core/lib/core/Query.js:65',  # noqa: E501
                'libtype': 'jit',
                'expected_name': 'get _hierarchy',
                'extras': {
                    'javascript': True,
                    'optimized': True,
                    'real_name': 'LazyCompile:get _hierarchy /apps/nodequark/etc/routes/node_modules/@netflix-internal/naql-core/lib/core/Query.js:65',  # noqa: E501
                    'v8_jit': True,
                },
            },
            {
                'input_name': 'LazyCompile:*a [eval]:1',
                'libtype': 'jit',
                'expected_name': 'a',
                'extras': {
                    'javascript': True,
                    'optimized': True,
                    'real_name': 'LazyCompile:*a [eval]:1',
                    'v8_jit': True,
                },
            },
        ]

        jsp = flamegraph.NodeJsStackProcessor(None, None)

        for test in tests:
            print(f"testing: {test['input_name']}")
            stack_frame = nflxprofile_pb2.StackFrame()
            stack_frame.function_name = test['input_name']
            stack_frame.libtype = test['libtype']

            [processed, extras] = jsp.process_frame(stack_frame)
            self.assertEqual(processed.function_name, test['expected_name'])
            self.assertEqual(dict_from_frame_extras(extras), test['extras'])
