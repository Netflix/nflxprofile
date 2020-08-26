import argparse
import functools
import json

from nflxprofile.convert.v8_cpuprofile import parse as v8_parse
from nflxprofile.flamegraph import JavaStackProcessor, NodeJsPackageStackProcessor, NodeJsStackProcessor, StackProcessor
from nflxprofile.flamegraph import get_flame_graph
from nflxprofile.nflxprofile_pb2 import Profile

STACK_PROCESSOR = {
    'default':  StackProcessor,
    'java': JavaStackProcessor,
    'nodejs':  NodeJsStackProcessor,
    'nodejs-package':  NodeJsPackageStackProcessor,
}


def get_input_format(input_format, input_files=[]):
    if input_format is None:
        if functools.reduce(lambda a, b: a and b.endswith(".cpuprofile"), input_files, True):
            input_format = 'v8'
        elif len(input_files) != 1:
            raise ValueError("Unable to infer input type. Please use --input-format")
        elif input_files[0].endswith(".nflxprofile"):
            input_format = 'nflxprofile'
        else:
            input_format = 'perf'
    return input_format


def get_output_format(output_format, output_file=None):
    if output_format is None:
        if output_file is None or output_file.endswith(".nflxprofile"):
            output_format = 'nflxprofile'
        elif output_file.endswith(".json"):
            output_format = 'tree'
        else:
            raise ValueError("Unable to infer output type. Please use --output-format")
    return output_format


def validate_input_output(input_format, output_format, input_files=[]):
    if input_format == 'nflxprofile':
        if output_format != 'tree':
            raise ValueError("Can't convert %s to %s" % (input_format, output_format))
    else:
        if output_format != 'nflxprofile':
            raise ValueError("Can't convert %s to %s" % (input_format, output_format))

    if input_format != 'v8' and len(input_files) > 1:
        raise ValueError("Only V8 .cpuprofile support multiple input files")


def main():
    parser = argparse.ArgumentParser(prog="nflxprofile", description=('Parse '
                                     'common profile/tracing formats into nflxprofile'))
    parser.add_argument('--output')
    parser.add_argument('--input-format', choices=['v8', 'perf', 'nflxprofile'])
    parser.add_argument('--output-format', choices=['nflxprofile', 'tree'])
    parser.add_argument('--force', action="store_true")
    parser.add_argument('--extra-options', type=json.loads)
    parser.add_argument('input', nargs="+")

    args = parser.parse_args()

    input_format = get_input_format(args.input_format, args.input)
    output_format = get_output_format(args.output_format, args.output)

    validate_input_output(input_format, output_format, args.input)

    if output_format == 'nflxprofile':
        out = args.output
        if not out:
            out = 'profile.nflxprofile'

        filenames = args.input
        extra_options = args.extra_options or {}

        profile = None
        if input_format == 'v8':
            profiles = []
            for filename in filenames:
                with open(filename, 'r') as f:
                    profiles.append(json.loads(f.read()))
            profile = v8_parse(profiles, **extra_options)

        with open(out, 'wb') as f:
            f.write(profile.SerializeToString())

    elif output_format == 'tree':
        out = args.output
        if not out:
            out = 'profile.json'

        filename = args.input[0]
        extra_options = args.extra_options or {}

        extra_options['stack_processor'] = STACK_PROCESSOR[extra_options.get('stack_processor', 'default')]

        tree = {}
        if input_format == 'nflxprofile':
            profile = Profile()
            with open(filename, 'rb') as f:
                profile.ParseFromString(f.read())
            tree = get_flame_graph(profile, {}, **extra_options)

        with open(out, 'w') as f:
            f.write(json.dumps(tree))
