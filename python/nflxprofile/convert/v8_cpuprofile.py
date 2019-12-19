__ALL__ = ['parse']

from nflxprofile import nflxprofile_pb2


def get_cpuprofiles(v8_profile):
    if type(v8_profile) == list:
        return v8_profile
    if "nodes" in v8_profile:
        return [v8_profile]
    raise TypeError("Unsupported V8 CPU Profile format")


def _generate_regular_stacks(nflxprofile_nodes, root_node_id):
    stacks = {}
    queue = []
    queue.append((root_node_id, None))

    nodes = {}
    for node in nflxprofile_nodes:
        nodes[node['id']] = node

    while queue:
        (nflxprofile_node_id, parent_node_id) = queue.pop(0)
        node = nodes[nflxprofile_node_id]

        stack_frame = nflxprofile_pb2.StackFrame()

        call_frame = node.get('callFrame', node)
        filename = call_frame['url']
        line = call_frame['lineNumber']
        column = call_frame['columnNumber']
        function_name = call_frame['functionName'] or '(anonymous)'
        children = node.get('children', [])

        libtype = ''
        if function_name in ['(garbage collector)', '(root)'] or not filename.startswith('file://'):
            libtype = 'kernel'
        elif 'node_modules' in filename:
            libtype = 'user'
        else:
            libtype = 'jit'

        if filename:
            if filename.startswith('file://'):
                filename = filename[7:]
            stack_frame.file.file_name = filename
            if line >= 0:
                stack_frame.file.line = line
            if column >= 0:
                stack_frame.file.column = column

        stack_frame.function_name = function_name
        stack_frame.libtype = libtype
        if not parent_node_id:
            stacks[nflxprofile_node_id] = [stack_frame]
        else:
            stacks[nflxprofile_node_id] = stacks[parent_node_id] + [stack_frame]
        for child_id in children:
            queue.append((child_id, nflxprofile_node_id))

    return stacks


def get_idle_ids(nodes):
    idle_ids = []
    for node in nodes:
        function_name = node['callFrame']['functionName']
        if function_name in ['(program)', '(idle)']:
            idle_ids.append(node['id'])
    return idle_ids


def get_comm(v8_profile, index, **extra_options):
    comms = extra_options.get('comms', [])
    if len(comms) <= index:
        return "(root)"
    return comms[index]


def get_pid(v8_profile, index, **extra_options):
    pids = extra_options.get('pids', [])
    if len(pids) <= index:
        return index + 1
    return pids[index]


def parse(data, **extra_options):
    """
    """
    v8_profiles = get_cpuprofiles(data)

    profile = nflxprofile_pb2.Profile()
    profile.nodes[0].function_name = 'root'
    profile.nodes[0].hit_count = 0
    profile.params['has_node_stack'] = 'true'
    profile.params['has_node_pid'] = 'true'
    profile.params['has_samples_pid'] = 'true'

    root_ids = []
    base_ids = []

    profile.start_time = profile.end_time = 0
    next_base_id = 0
    for v8_profile in v8_profiles:
        if profile.start_time == 0:
            profile.start_time = v8_profile['startTime']
        if profile.end_time == 0:
            profile.end_time = v8_profile['endTime']
        profile.start_time = min(profile.start_time, v8_profile['startTime'])
        profile.end_time = max(profile.end_time, v8_profile['endTime'])
        base_ids.append(next_base_id)
        highest_id = 0
        for index, node in enumerate(v8_profile['nodes']):
            highest_id = max(node['id'], highest_id)
        next_base_id += highest_id + 1

    samples = []

    for v8_profile_idx, v8_profile in enumerate(v8_profiles):
        comm = get_comm(v8_profile, v8_profile_idx, **extra_options)
        pid = get_pid(v8_profile, v8_profile_idx, **extra_options)
        base_id = base_ids[v8_profile_idx]

        # TODO(mmarchini): detect root instead of assuming it is 1
        root_ids.append(base_id + 1)
        stacks = _generate_regular_stacks(v8_profile['nodes'], 1)

        idle_ids = get_idle_ids(v8_profile['nodes'])

        node_id_cache = []

        last_timestamp = v8_profile['startTime']
        for index, node_id in enumerate(v8_profile['samples']):
            if node_id in idle_ids:
                continue

            stack = None
            if node_id not in node_id_cache:
                stack = stacks[node_id]
                node_id_cache.append(node_id)

            node_id = base_id + node_id

            if stack:
                profile.nodes[node_id].function_name = comm
                profile.nodes[node_id].pid = pid
                profile.nodes[node_id].hit_count = 0
                profile.nodes[node_id].stack.extend(stack)

            last_timestamp += v8_profile['timeDeltas'][index]

            samples.append((last_timestamp, node_id, pid))
            profile.nodes[node_id].hit_count += 1

    samples = sorted(samples, key=lambda e: e[0])
    last_timestamp = profile.start_time
    profile.start_time = profile.start_time / 1000000.
    profile.end_time = profile.end_time / 1000000.
    for timestamp, node_id, pid in samples:
        profile.samples.append(node_id)
        profile.samples_pid.append(pid)
        delta = (timestamp - last_timestamp) / 1000000.
        profile.time_deltas.append(delta)
        last_timestamp = timestamp

    return profile
