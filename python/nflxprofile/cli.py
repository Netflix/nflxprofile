import json
import argparse

from nflxprofile.convert.v8_cpuprofile import parse as v8_parse

def main():
    parser = argparse.ArgumentParser(prog="nflxprofile", description='Parse common profile/tracing formats into nflxprofile')
    parser.add_argument('input')
    parser.add_argument('--output')
    parser.add_argument('--force', action="store_true")

    args = parser.parse_args()

    original = args.input
    out = args.output
    if not out:
        out = original.rsplit('.', 1)[0] + '.nflxprofile'

    profile = None
    with open(original, 'r') as f:
        profile = v8_parse(json.loads(f.read()))

    with open(out, 'wb') as f:
        f.write(profile.SerializeToString())
