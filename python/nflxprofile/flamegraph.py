"""Flame graph module for generating flame graphs from nflxprofile profiles."""

import math
from nflxprofile import nflxprofile_pb2

# pylint: disable=too-few-public-methods

def _get_child(node, name, libtype):
    for child in node['children']:
        if child['name'] == name and child['libtype'] == libtype:
            return child
    return None


def _generate_regular_stacks(nflxprofile_nodes, root_node_id):
    stacks = {}
    queue = []
    queue.append((root_node_id, None))

    while queue:
        (nflxprofile_node_id, parent_node_id) = queue.pop(0)
        nflxprofile_node = nflxprofile_nodes[nflxprofile_node_id]
        stack_frame = nflxprofile_pb2.StackFrame()
        stack_frame.function_name = nflxprofile_node.function_name
        stack_frame.libtype = nflxprofile_node.libtype
        if not parent_node_id:
            stacks[nflxprofile_node_id] = [stack_frame]
        else:
            stacks[nflxprofile_node_id] = stacks[parent_node_id] + [stack_frame]
        for child_id in nflxprofile_node.children:
            queue.append((child_id, nflxprofile_node_id))

    return stacks


def _generate_package_name_stacks(nflxprofile_nodes):
    stacks = {}
    for key in nflxprofile_nodes:
        nflxprofile_node = nflxprofile_nodes[key]
        function_name = nflxprofile_node.function_name.split(';')[0]
        function_name_arr = function_name.split('/')
        stack_arr = []
        for package_name in function_name_arr:
            stack_frame = nflxprofile_pb2.StackFrame()
            stack_frame.function_name = package_name
            stack_frame.libtype = nflxprofile_node.libtype
            stack_arr.append(stack_frame)
        stacks[key] = stack_arr

    return stacks


def _generate_stacks(nflxprofile_nodes, root_node_id, package_name=False):
    if package_name:
        return _generate_package_name_stacks(nflxprofile_nodes)
    return _generate_regular_stacks(nflxprofile_nodes, root_node_id)


def _get_stack(nflxprofile_nodes, node_id, has_node_stack=False, pid_comm=None, **args):
    """Get node stack using parent pointers or predefined stack."""
    inverted = args.get("inverted", False)
    package_name = args.get("package_name", False)

    stack = []

    # package name, only need first node
    if package_name:
        function_name = nflxprofile_nodes[node_id].function_name.split(';')[0]
        function_name_arr = function_name.split('/')
        for name in function_name_arr:
            stack_frame = nflxprofile_pb2.StackFrame()
            stack_frame.function_name = name
            stack_frame.libtype = nflxprofile_nodes[node_id].libtype
            stack.append(stack_frame)
        if inverted:
            return reversed(stack)
        return stack

    # has node stack calculated, returning that
    if has_node_stack:
        function_name = nflxprofile_nodes[node_id].function_name
        pid = nflxprofile_nodes[node_id].pid
        if pid_comm and pid and pid in pid_comm:
            function_name = pid_comm[pid]
        stack_frame = nflxprofile_pb2.StackFrame()
        stack_frame.function_name = function_name
        stack_frame.libtype = nflxprofile_nodes[node_id].libtype
        stack = [stack_frame] + list(nflxprofile_nodes[node_id].stack)
        if inverted:
            return reversed(stack)
        return stack

    # need to use parent id
    nflxprofile_node_id = node_id
    while True:
        nflxprofile_node = nflxprofile_nodes[nflxprofile_node_id]
        if inverted:
            stack.append((nflxprofile_node.function_name, nflxprofile_node.libtype))
        else:
            stack_frame = nflxprofile_pb2.StackFrame()
            stack_frame.function_name = nflxprofile_node.function_name
            stack_frame.libtype = nflxprofile_node.libtype
            stack.insert(
                0, stack_frame)
        if not nflxprofile_nodes[nflxprofile_node_id].parent:
            break
        nflxprofile_node_id = nflxprofile_node.parent
    return stack


class SampleFilter:
    """Interface for sample filters.

    Extend this class and override should_skip to create a new filter.
    """

    # pylint: disable=unused-argument
    def __init__(self, profile, **args):
        """Default constructor for a filter."""
        self.profile = profile

    # pylint: disable=no-self-use
    def should_skip(self, sample, index, current_time):
        """Returns false if a given sample shouldn't be processed."""
        return False


class RangeSampleFilter(SampleFilter):
    """Filter all samples within a given range."""

    def __init__(self, profile, range_start=None, range_end=None, **args):
        """Range filter constructor."""
        super().__init__(profile)
        if range_start is None or range_end is None:
            self.range_start = self.range_end = None
            return
        start_time = math.floor(profile.start_time)
        self.range_start = (start_time + range_start)
        self.range_end = (start_time + range_end)

    def should_skip(self, sample, index, current_time):
        """Returns false if a given sample is not in range."""
        if self.range_start is None or self.range_end is None:
            return False
        return not self.range_start <= current_time < self.range_end


class CPUSampleFilter(SampleFilter):
    """Filter all samples for a given CPU."""

    def __init__(self, profile, cpu=None, **args):
        """CPU filter constructor."""
        super().__init__(profile)
        self.cpu = cpu
        self.samples_cpu = None

        if 'has_samples_cpu' not in profile.params:
            return
        if profile.params['has_samples_cpu'] != 'true':
            return

        self.samples_cpu = profile.samples_cpu

    def should_skip(self, sample, index, current_time):
        """Returns false if a given sample was not running on this CPU."""
        if self.cpu is None or self.samples_cpu is None:
            return False
        return self.cpu != self.samples_cpu[index]


class PIDSampleFilter(SampleFilter):
    """Filter all samples for a given PID."""

    def __init__(self, profile, pid=None, **args):
        """PID filter constructor."""
        super().__init__(profile)
        self.pid = pid
        self.samples_pid = None

        if 'has_samples_pid' not in profile.params:
            return
        if profile.params['has_samples_pid'] != 'true':
            return

        self.samples_pid = profile.samples_pid

    def should_skip(self, sample, index, current_time):
        """Returns false if a given sample doesn't include PID."""
        if self.pid is None or self.samples_pid is None:
            return False
        return self.pid != self.samples_pid[index]


class TIDSampleFilter(SampleFilter):
    """Filter all samples for a given TID."""

    def __init__(self, profile, tid=None, **args):
        """PID filter constructor."""
        super().__init__(profile)
        self.tid = tid
        self.samples_tid = None

        if 'has_samples_tid' not in profile.params:
            return
        if profile.params['has_samples_tid'] != 'true':
            return

        self.samples_tid = profile.samples_tid

    def should_skip(self, sample, index, current_time):
        """Returns false if a given sample doesn't include TID."""
        if self.tid is None or self.samples_tid is None:
            return False
        return self.tid != self.samples_tid[index]

# pylint: disable=too-many-locals
# pylint: disable=too-many-branches
# pylint: disable=too-many-statements
def get_flame_graph(profile, pid_comm, **args):
    """Generate flame graph from a nflxprofile profile."""
    inverted = args.get("inverted", False)
    package_name = args.get("package_name", False)
    use_sample_value = args.get("use_sample_value", False)

    nodes = profile.nodes
    root_id = 0

    samples = profile.samples
    time_deltas = profile.time_deltas
    start_time = profile.start_time

    sample_filters = [
        RangeSampleFilter(profile, **args),
        CPUSampleFilter(profile, **args),
        PIDSampleFilter(profile, **args),
        TIDSampleFilter(profile, **args)
    ]

    root = {
        'name': 'root',
        'libtype': '',
        'value': 0,
        'children': []
    }
    current_time = start_time + time_deltas[0]

    has_node_stack = \
        'has_node_stack' in profile.params and profile.params['has_node_stack'] == 'true'
    has_parent = 'has_parent' in profile.params and profile.params['has_parent'] == 'true'

    samples_value = None
    if 'hasValues' in profile.params and profile.params['hasValues'] == 'true':
        samples_value = profile.samples_value

    stacks = None
    if (not has_node_stack) and (not has_parent):
        # don't have stacks or parent pointer, generating stacks manually
        stacks = _generate_stacks(nodes, root_id, package_name)

    for index, sample in enumerate(samples):
        if index == (len(samples) - 1):  # last sample
            break
        delta = time_deltas[index + 1]
        current_time += delta

        should_skip = False
        for sample_filter in sample_filters:
            should_skip = sample_filter.should_skip(sample, index, current_time)
            if should_skip:
                break
        if should_skip:
            continue

        sample_value = samples_value[index] if samples_value else None

        if stacks:
            stack = stacks[sample] if not inverted else reversed(stacks[sample])
        else:
            stack = _get_stack(nodes, sample, has_node_stack, pid_comm, **args)
        value = 1
        if use_sample_value and sample_value:
            value = sample_value
        current_node = root
        for frame in stack:
            child = _get_child(current_node, frame.function_name, frame.libtype)
            if child is None:
                child = {
                    'name': frame.function_name,
                    'libtype': frame.libtype,
                    'value': 0,
                    'children': []
                }
                current_node['children'].append(child)
            extras = child.get('extras', {})

            if frame.file.file_name:
                extras = child.get('extras', {})
                extras['file'] = frame.file.file_name
                child['extras'] = extras
            child['extras'] = extras
            current_node = child
        current_node['value'] = current_node['value'] + value
    return root
