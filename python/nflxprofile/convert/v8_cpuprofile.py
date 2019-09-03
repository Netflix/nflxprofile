__ALL__ = ['parse']

from nflxprofile import nflxprofile_pb2


def get_cpuprofiles(chrome_profile):
    if "nodes" in chrome_profile:
        return [chrome_profile]
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
            if  filename.startswith('file://'):
                filename = filename[7:]
            stack_frame.file.file_name = filename
            stack_frame.file.line = line
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

def parse(profile):
    profile = get_cpuprofiles(profile)
    # TODO (mmarchini): support multiple profiles
    nodes = profile[0]

    profile = nflxprofile_pb2.Profile()
    profile.nodes[0].function_name = 'root'
    profile.nodes[0].hit_count = 0
    profile.nodes[0].children.append(1)
    profile.params['has_node_stack'] = 'true'

    profile.start_time = nodes['startTime']
    profile.end_time = nodes['endTime']
    profile.end_time = nodes['endTime']

    stacks = _generate_regular_stacks(nodes['nodes'], 1)

    idle_ids = get_idle_ids(nodes['nodes'])

    node_id_cache = []

    profile.time_deltas.append(0)
    for index, node_id in enumerate(nodes['samples']):
        if node_id in idle_ids:
            continue

        if node_id not in node_id_cache:
            stack = stacks[node_id]
            profile.nodes[node_id].function_name = '(root)'
            profile.nodes[node_id].hit_count = 0
            profile.nodes[node_id].stack.extend(stack)
            node_id_cache.append(node_id)

        profile.samples.append(node_id)
        profile.time_deltas.append(nodes['timeDeltas'][index])
        profile.nodes[node_id].hit_count += 1

    return profile
