import json
import unittest

from nflxprofile import nflxprofile_pb2
from nflxprofile.flamegraph import NodeJsStackProcessor, get_flame_graph


class TestNodeJsStackProcessor(unittest.TestCase):

    def test_nodejs1(self):
        profile = nflxprofile_pb2.Profile()
        with open("test/fixtures/nodejs1.nflxprofile", "rb") as f:
            profile.ParseFromString(f.read())

        expected = None
        with open("test/fixtures/nodejs1.json", "r") as f:
            expected = json.loads(f.read())

        fg = get_flame_graph(profile, None,
                             stack_processor=NodeJsStackProcessor)
        self.assertDictEqual(fg, expected)
