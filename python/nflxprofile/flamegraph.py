"""Flame graph module for generating flame graphs from nflxprofile profiles."""

__ALL__ = ['get_flame_graph',
           'StackProcessor',
           'JavaStackProcessor',
           'NodeJsStackProcessor',
           'NodeJsPackageStackProcessor']

import math
import os
import pathlib

from nflxprofile import nflxprofile_pb2


def _get_child(node, frame, ignore_libtype):
    """Docstring for public method."""
    if isinstance(frame, dict):
        name = frame.get('name', "").strip()
        libtype = frame.get("libtype", "")
        filename = frame.get('extras', {}).get('file', "")
    else:
        name = frame.function_name.strip()
        libtype = frame.libtype
        filename = frame.file.file_name or ""
        if filename:
            filename = "%s:%d" % (filename, frame.file.line or 0)
    for child in node['children']:
        if child['name'].strip() == name:
            if ignore_libtype or child['libtype'] == libtype:
                child_file = child.get('extras', {}).get('file', "")
                if filename == child_file:
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
        function_name = nflxprofile_nodes[node_id].function_name
        if has_node_stack:
            # uses node stack format, can't use node's function name
            node_stack = nflxprofile_nodes[node_id].stack
            function_name = node_stack[-1].function_name
        sanitized_function_name = function_name.split(';')[0]
        function_name_arr = sanitized_function_name.split('/')
        for name in function_name_arr:
            stack_frame = nflxprofile_pb2.StackFrame()
            stack_frame.function_name = name
            stack_frame.libtype = nflxprofile_nodes[node_id].libtype
            stack.append(stack_frame)
        if inverted:
            return stack[::-1]
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
            return stack[::-1]
        return stack

    # need to use parent id
    nflxprofile_node_id = node_id
    while True:
        nflxprofile_node = nflxprofile_nodes[nflxprofile_node_id]
        stack_frame = nflxprofile_pb2.StackFrame()
        stack_frame.function_name = nflxprofile_node.function_name
        stack_frame.libtype = nflxprofile_node.libtype
        if inverted:
            stack.append(stack_frame)
        else:
            stack.insert(0, stack_frame)
        if not nflxprofile_nodes[nflxprofile_node_id].parent:
            break
        nflxprofile_node_id = nflxprofile_node.parent
    return stack


class FrameExtras:
    """Generic class to store extra information about a stack frame."""

    def __init__(self):
        """Constructor."""
        self.v8_jit = False
        self.javascript = False
        self.real_name = ""
        self.optimized = None

    def __repr__(self):
        return ("FrameExtras(v8_jit=%s, javascript=%s, real_name=%s, optimized=%s)"
                % (self.v8_jit, self.javascript, self.real_name, self.optimized))


class Frame:
    def __init__(self, frame):
        self.frame = frame

    def __getattr__(self, name):
        return getattr(self.frame, name)


class StackProcessor:
    """Processes a stack trace, extend it to add custom processing."""

    def __init__(self, root, profile, **args):
        """Constructor."""
        self.root_node = root
        self.current_node = root
        self.ignore_libtype = args.get("ignore_libtype", False)
        self.middle_out = args.get("middle_out", None)

    def process_frame(self, frame):
        """Process one frame, returning the processed frame plus extras."""
        return frame, FrameExtras()

    # pylint: disable=no-self-use
    def should_skip_frame(self, frame, frame_extras, value):
        """Check if this frame should be skipped."""
        return False

    def process_extras(self, child, frame, frame_extras, value):
        """Process extras and save it in the given node."""
        extras = child.get('extras', {})
        if frame.file.file_name:
            if 'file' not in extras:
                extras['file'] = frame.file.file_name
                if extras['file']:
                    extras['file'] = ('%s:%d' % (extras['file'], frame.file.line))
        if bool(extras):
            child['extras'] = extras

    def process(self, stack, value):
        """Processes a stack trace.

        You probably want to avoid overriding this method. Override other
        methods to customize behavior instead.
        """
        middle_out_filter = True
        for i, frame in enumerate(stack):
            frame, frame_extras = self.process_frame(frame)
            if self.should_skip_frame(frame, frame_extras, value):
                continue

            if self.middle_out and middle_out_filter:
                # middle out merge and no stack match yet
                try:
                    next_frame = stack[i + 1]
                except IndexError:
                    # this is the last frame
                    continue
                # checking next frame name for a match
                if self.middle_out in next_frame.function_name:
                    # match on the next frame
                    # process this and everything from here
                    middle_out_filter = False
                else:
                    # no match
                    # skip frame
                    continue

            child = _get_child(self.current_node, frame, self.ignore_libtype)
            if child is None:
                child = {
                    'name': frame.function_name.strip(),
                    'value': 0,
                    'children': []
                }
                child['libtype'] = "" if self.ignore_libtype else frame.libtype
                self.current_node['children'].append(child)
            self.process_extras(child, frame, frame_extras, value)
            self.current_node = child
        # if the whole stack was skipped, current_node is still root
        # value goes to root
        self.current_node['value'] = self.current_node['value'] + value
        # set current node back to root
        self.current_node = self.root_node


class JavaStackProcessor(StackProcessor):
    """Java stack processor.

    Sanitize function names, remove interpreter frames.
    """

    def __init__(self, root, profile, **args):
        """Constructor."""
        super().__init__(root, profile, **args)

    def should_skip_frame(self, frame, frame_extras, value):
        """Skip Interpreter frames."""
        if "Interpreter" in frame.function_name:
            return True
        return False

    def process_frame(self, frame):
        """Process frame."""
        processed_frame = nflxprofile_pb2.StackFrame()
        processed_frame.CopyFrom(frame)
        name = frame.function_name
        name_parts = name.split('::')

        class_name = name_parts[0]
        class_name = class_name.split('$$')[0]

        if frame.libtype and frame.libtype in ['jit', 'inlined'] and class_name.startswith("L"):
            class_name = class_name[1:]

        if class_name.endswith(';'):
            class_name = class_name[:-1]

        class_name = class_name.replace('/', '.')

        if len(name_parts) > 1:
            processed_frame.function_name = class_name + "::" + name_parts[1]
        else:
            processed_frame.function_name = class_name

        return processed_frame, FrameExtras()


class NodeJsPackageStackProcessor(StackProcessor):

    def __init__(self, root, profile, **args):
        """Constructor."""
        super().__init__(root, profile, **args)
        self.current_package = None
        self.packages_cache = {}

    def get_package(self, frame):
        name = frame.function_name
        if name in self.packages_cache:
            return self.packages_cache[name]

        package = None
        if name.startswith("LazyCompile:") or name.startswith("InterpretedFunction:"):
            name = name[name.index(":") + 1:]
            if name and name[0] == '*':
                name = name[1:]

            if " " in name:
                package = name[name.index(" ") + 1:]

        if package is not None:
            if ":" in package:
                package = package.rsplit(":", 1)[0]
            if "node_modules" in package:
                package = pathlib.Path(package.rsplit("node_modules", 1)[1])
                if package.parts[1].startswith("@"):
                    package = os.path.join(*package.parts[1:3])
                else:
                    package = package.parts[1]
            elif package.startswith("/") or "[eval" in package:
                return "(app code)"
            else:
                package = "(node api)"
        else:
            if frame.libtype == 'kernel':
                return '(kernel)'
            else:
                return '(native)'

        return package

    def should_skip(self, name):
        # We'll skip for known, non-expensive builtins which can appear between
        # JS frames. Showing those would fragment the FlameGraph unecessarily.
        if 'ArgumentsAdaptorTrampoline' in name:
            return True
        if name.startswith('Builtin'):
            if 'Construct' in name:
                return True
            if 'LoadIC' in name or 'StoreIC' in name:
                return True
            if 'InterpreterEntryTrampoline' in name:
                return True
        if name.startswith('BytecodeHandler'):
            return True
        return False

    def process(self, stack, value):
        # We always start with native
        current_frame = nflxprofile_pb2.StackFrame()
        current_frame.function_name = "(native)"
        current_frame.libtype = ""
        processed_stack = []
        current_stack = []
        for frame in stack:
            package = self.get_package(frame)

            if package == current_frame.function_name or self.should_skip(frame.function_name):
                current_stack.append(frame)
                continue

            processed_stack.append(current_frame)

            current_frame = nflxprofile_pb2.StackFrame()
            current_frame.function_name = package
            current_frame.libtype = ""
            current_stack = []

        processed_stack.append(current_frame)

        return super().process(processed_stack, value)


class NodeJsStackProcessor(StackProcessor):
    """Node.js mode stack processor.

    Sanitize JIT function names, extract file name from frame name, group
    interpreted and compiled function, flag V8 builtins, hide
    ArgumentsAdaptorTrampoline frames (but store count in the next frame so we
    can exhibit this information on the interface).
    """

    def __init__(self, root, profile, **args):
        """Constructor."""
        super().__init__(root, profile, **args)
        self.argument_adaptor = None

    def should_skip_frame(self, frame, frame_extras, value):
        """Skip ArgumentsAdaptorTrampoline.

        ArgumentsAdaptorTrampoline frames are inserted between calls when the
        caller calls the callee with wrong signature. While this information is
        relevant (since ArgumentsAdaptorTrampoline is not free), it can mess
        with frame grouping. Skipping this frame makes sense and we can show
        information about it in the following frame when hovering it.
        """
        if "ArgumentsAdaptorTrampoline" in frame.function_name:
            self.argument_adaptor = value
            return True
        return False

    def process_extras(self, child, frame, frame_extras, value):
        """Add Node.js specific extras.

        Add % of times a function was called with mismatched arguments, % of
        times it executed JIT instead of intepreted, as well as some metadata
        used for coloring the flamegraph.
        """
        extras = child.get('extras', {'optimized': 0})
        extras['javascript'] = frame_extras.javascript
        extras['v8_jit'] = frame_extras.v8_jit
        extras['optimized'] = extras['optimized'] + (frame_extras.optimized and value or 0)
        extras['realName'] = frame_extras.real_name
        if self.argument_adaptor:
            extras['argumentAdaptor'] = extras.get('argumentAdaptor', 0) + self.argument_adaptor
            self.argument_adaptor = None
        child['extras'] = extras
        super().process_extras(child, frame, frame_extras, value)

    def process_frame(self, frame):
        """Process frame.

        Sanitize JIT function names, extract file name from frame name,
        generate some metadata used by other methods.
        """
        processed_frame = Frame(frame)
        frame_extras = FrameExtras()
        frame_extras.v8_jit = False
        frame_extras.javascript = False
        name = frame.function_name

        frame_extras.real_name = name

        if name.startswith("LazyCompile:") or name.startswith("InterpretedFunction:"):
            frame_extras.v8_jit = True
            frame_extras.javascript = True
            frame_extras.optimized = name.startswith("LazyCompile:")

            name = name[name.index(":") + 1:]
            if name and name[0] == '*':
                name = name[1:]

            if " " in name:
                frame.file.file_name = name[name.index(" ") + 1:]
                if frame.file.file_name:
                    name = name[:name.index(" ")]
            processed_frame.function_name = name or "(anonymous)"

        return processed_frame, frame_extras


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
    cpu = args.get("cpu", None)
    pid = args.get("pid", None)
    tid = args.get("tid", None)
    stack_processor_class = args.get("stack_processor", StackProcessor)

    nodes = profile.nodes
    root_id = 0

    samples = profile.samples
    time_deltas = profile.time_deltas
    start_time = profile.start_time
    current_time = start_time + time_deltas[0]

    has_samples_cpu = \
        'has_samples_cpu' in profile.params and profile.params['has_samples_cpu'] == 'true'

    has_samples_pid = \
        'has_samples_pid' in profile.params and profile.params['has_samples_pid'] == 'true'

    has_samples_tid = \
        'has_samples_tid' in profile.params and profile.params['has_samples_tid'] == 'true'

    has_node_stack = \
        'has_node_stack' in profile.params and profile.params['has_node_stack'] == 'true'
    has_parent = \
        'has_parent' in profile.params and profile.params['has_parent'] == 'true'

    samples_value = None
    if 'hasValues' in profile.params and profile.params['hasValues'] == 'true':
        samples_value = profile.samples_value

    sample_filters = [
        RangeSampleFilter(profile, **args)
    ]

    if has_samples_cpu and cpu:
        sample_filters.append(CPUSampleFilter(profile, **args))
    if has_samples_pid and pid:
        sample_filters.append(PIDSampleFilter(profile, **args))
    if has_samples_tid and tid:
        sample_filters.append(TIDSampleFilter(profile, **args))

    stacks = None
    if (not has_node_stack) and (not has_parent):
        # don't have stacks or parent pointer, generating stacks manually
        # case for very old nflxprofile
        stacks = _generate_stacks(nodes, root_id, package_name)

    aggregated_samples = {}
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

        sample_value = 1
        if use_sample_value:
            sample_value = samples_value[index] if samples_value else None

        if sample not in aggregated_samples:
            aggregated_samples[sample] = 0
        aggregated_samples[sample] += sample_value

    root = {
        'name': 'root',
        'libtype': '',
        'value': 0,
        'children': []
    }

    stack_processor = stack_processor_class(root, profile, **args)

    for sample_id in aggregated_samples:
        sample_value = aggregated_samples[sample_id]

        if stacks:
            stack = stacks[sample_id] if not inverted else stacks[sample_id][::-1]
        else:
            stack = _get_stack(nodes, sample_id, has_node_stack, pid_comm, **args)

        stack_processor.process(stack, sample_value)
    return root
