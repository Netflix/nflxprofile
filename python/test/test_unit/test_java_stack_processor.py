
import unittest

from nflxprofile import flamegraph, nflxprofile_pb2


class TestJavaStackProcessor(unittest.TestCase):

    def test_java_naming(self):
        tests = [
            {
                'input_name': 'Ljava/util/concurrent/Executors$RunnableAdapter;::call',
                'libtype': 'jit',
                'expected_name': 'java.util.concurrent.Executors$RunnableAdapter::call',
            },
            {
                'input_name': 'Ljava/util/concurrent/Executors$RunnableAdapter;::call',
                'libtype': 'inlined',
                'expected_name': 'java.util.concurrent.Executors$RunnableAdapter::call',
            },
            {
                'input_name': 'Ljava/util/concurrent/FutureTask;::run',
                'libtype': 'inlined',
                'expected_name': 'java.util.concurrent.FutureTask::run',
            },
            {
                'input_name': 'Lcom/netflix/napa/SearchService$$EnhancerBySpringCGLIB$$65a2ea77;::searchNapa',
                'libtype': 'jit',
                'expected_name': 'com.netflix.napa.SearchService::searchNapa',
            },
            {
                'input_name': 'Lio/grpc/stub/ServerCalls$UnaryServerCallHandler$UnaryServerCallListener;::onHalfClose',
                'libtype': 'jit',
                'expected_name': 'io.grpc.stub.ServerCalls$UnaryServerCallHandler$UnaryServerCallListener::onHalfClose',
            },
            {
                'input_name': 'Lcom/netflix/springboot/sso/grpcextensions/GrpcContextAspect$$Lambda$2611/1287052643;::call',  # noqa: E501
                'libtype': 'inlined',
                'expected_name': 'com.netflix.springboot.sso.grpcextensions.GrpcContextAspect::call',
            },
        ]

        jsp = flamegraph.JavaStackProcessor(None, None)

        for test in tests:
            stack_frame = nflxprofile_pb2.StackFrame()
            stack_frame.function_name = test['input_name']
            stack_frame.libtype = test['libtype']

            [processed, extras] = jsp.process_frame(stack_frame)
            self.assertEqual(processed.function_name, test['expected_name'])
