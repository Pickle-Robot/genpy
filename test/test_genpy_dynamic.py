# Software License Agreement (BSD License)
#
# Copyright (c) 2008, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of Willow Garage, Inc. nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

try:
    from cStringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO
import sys
import time


def test_generate_dynamic():
    import genpy
    from genpy.dynamic import generate_dynamic
    msgs = generate_dynamic('gd_msgs/EasyString', 'string data\n')
    assert ['gd_msgs/EasyString'] == list(msgs.keys())
    m_cls = msgs['gd_msgs/EasyString']
    m_instance = m_cls()
    m_instance.data = 'foo'
    buff = StringIO()
    m_instance.serialize(buff)
    m_instance2 = m_cls().deserialize(buff.getvalue())
    assert m_instance == m_instance2

    try:
        msgs = generate_dynamic('gd_msgs/MyAcceleration', 'float32 acceleration  # in m/s\xc2\xb2\n')
    except UnicodeDecodeError:
        assert False, "Can't handle UTF-8 in comments"

    try:
        char = unichr
    except NameError:
        char = chr
    m_instance.data = 'foo' + char(1234)
    buff = StringIO()
    m_instance.serialize(buff)
    m_instance2 = m_cls().deserialize(buff.getvalue())
    if sys.hexversion < 0x03000000:
        # python 2 requires manual decode into unicode
        m_instance2.data = m_instance2.data.decode('utf-8')
    assert m_instance == m_instance2

    # 'probot_msgs' is a test for #1183, failure if the package no longer exists
    msgs = generate_dynamic('gd_msgs/MoveArmState', """Header header
probot_msgs/ControllerStatus status

#Current arm configuration
probot_msgs/JointState[] configuration
#Goal arm configuration
probot_msgs/JointState[] goal

================================================================================
MSG: std_msgs/Header
#Standard metadata for higher-level flow data types
#sequence ID: consecutively increasing ID
uint32 seq
#Two-integer timestamp that is expressed as:
# * stamp.secs: seconds (stamp_secs) since epoch
# * stamp.nsecs: nanoseconds since stamp_secs
# time-handling sugar is provided by the client library
time stamp
#Frame this data is associated with
# 0: no frame
# 1: global frame
string frame_id

================================================================================
MSG: probot_msgs/ControllerStatus
# This message defines the expected format for Controller Status messages
# Embed this in the feedback state message of highlevel controllers
byte UNDEFINED=0
byte SUCCESS=1
byte ABORTED=2
byte PREEMPTED=3
byte ACTIVE=4

# Status of the controller = {UNDEFINED, SUCCESS, ABORTED, PREEMPTED, ACTIVE}
byte value

#Comment for debug
string comment
================================================================================
MSG: probot_msgs/JointState
string name
float64 position
float64 velocity
float64 applied_effort
float64 commanded_effort
byte is_calibrated

""")
    assert {'gd_msgs/MoveArmState', 'probot_msgs/JointState', 'probot_msgs/ControllerStatus', 'std_msgs/Header'} == set(msgs.keys())
    m_instance1 = msgs['std_msgs/Header']()  # make sure default constructor works
    m_instance2 = msgs['std_msgs/Header'](stamp=genpy.Time.from_sec(time.time()), frame_id='foo-%s' % time.time(), seq=12390)
    _test_ser_deser(m_instance2, m_instance1)

    m_instance1 = msgs['probot_msgs/ControllerStatus']()
    m_instance2 = msgs['probot_msgs/ControllerStatus'](value=4, comment=str(time.time()))
    d = {'UNDEFINED': 0, 'SUCCESS': 1, 'ABORTED': 2, 'PREEMPTED': 3, 'ACTIVE': 4}
    for k, v in d.items():
        assert v == getattr(m_instance1, k)
    _test_ser_deser(m_instance2, m_instance1)

    m_instance1 = msgs['probot_msgs/JointState']()
    m_instance2 = msgs['probot_msgs/JointState'](position=time.time(), velocity=time.time(), applied_effort=time.time(), commanded_effort=time.time(), is_calibrated=2)
    _test_ser_deser(m_instance2, m_instance1)

    m_instance1 = msgs['gd_msgs/MoveArmState']()
    js = msgs['probot_msgs/JointState']
    config = []
    goal = []
    # generate some data for config/goal
    for i in range(0, 10):
        config.append(js(position=time.time(), velocity=time.time(), applied_effort=time.time(), commanded_effort=time.time(), is_calibrated=2))
        goal.append(js(position=time.time(), velocity=time.time(), applied_effort=time.time(), commanded_effort=time.time(), is_calibrated=2))
    m_instance2 = msgs['gd_msgs/MoveArmState'](header=msgs['std_msgs/Header'](),
                                               status=msgs['probot_msgs/ControllerStatus'](),
                                               configuration=config, goal=goal)
    _test_ser_deser(m_instance2, m_instance1)


def _test_ser_deser(m_instance1, m_instance2):
    buff = StringIO()
    m_instance1.serialize(buff)
    m_instance2.deserialize(buff.getvalue())
    assert m_instance1 == m_instance2


def _build_dynamic_source(core_type, msg_cat):
    """Build rewritten dynamic module source without importing it."""
    from io import StringIO as TextIO

    from genmsg import MsgContext
    import genmsg.msg_loader
    from genpy.dynamic import _generate_dynamic_specs, _gen_dyn_modify_references
    from genpy.generator import msg_generator

    msg_context = MsgContext.create_default()
    msg_cat = msg_cat.replace('roslib/Header', 'std_msgs/Header')
    splits = msg_cat.split('\n' + '=' * 80 + '\n')
    core_msg = splits[0]
    deps_msgs = splits[1:]
    specs = {core_type: genmsg.msg_loader.load_msg_from_string(msg_context, core_msg, core_type)}
    for dep_msg in deps_msgs:
        dep_type, dep_spec = _generate_dynamic_specs(msg_context, specs, dep_msg)
        specs[dep_type] = dep_spec
    msg_context = genmsg.msg_loader.MsgContext.create_default()
    for t, spec in specs.items():
        msg_context.register(t, spec)
    buff = TextIO()
    for t, spec in specs.items():
        for line in msg_generator(msg_context, spec, {}):
            buff.write(_gen_dyn_modify_references(line, t, list(specs.keys())) + '\n')
    return 'from __future__ import annotations\n' + buff.getvalue()


def test_dynamic_generated_source_has_no_installed_imports():
    # Regression test for bag playback: dependent types embedded in the bag
    # must not import installed packages from PYTHONPATH.
    from genpy.dynamic import _gen_dyn_modify_references

    types = ['gd_msgs/MoveArmState', 'probot_msgs/JointState', 'std_msgs/Header']
    import_line = 'from probot_msgs.msg._JointState import JointState as probot_msgs_msg_JointState'
    ctor_line = '        val1 = probot_msgs_msg_JointState()'

    assert _gen_dyn_modify_references(import_line, 'gd_msgs/MoveArmState', types).strip() == ''
    rewritten_ctor = _gen_dyn_modify_references(ctor_line, 'gd_msgs/MoveArmState', types)
    assert 'probot_msgs.msg._JointState' not in rewritten_ctor
    assert 'probot_msgs_msg_JointState' not in rewritten_ctor
    assert '_probot_msgs__JointState()' in rewritten_ctor

    msg_cat = """Header header
probot_msgs/JointState[] configuration

================================================================================
MSG: std_msgs/Header
uint32 seq
time stamp
string frame_id

================================================================================
MSG: probot_msgs/JointState
string name
float64 position
"""
    source = _build_dynamic_source('gd_msgs/MoveArmState', msg_cat)
    assert 'from probot_msgs.msg._' not in source
    assert 'from std_msgs.msg._' not in source
    assert 'probot_msgs_msg_JointState' not in source
    assert 'std_msgs_msg_Header' not in source
    assert '_probot_msgs__JointState' in source
    assert '_std_msgs__Header' in source


def test_serialize_exception():
    import genpy
    from genpy.dynamic import generate_dynamic
    msgs = generate_dynamic('gd_msgs/EasyInt32', 'int32 data\n')
    assert ['gd_msgs/EasyInt32'] == list(msgs.keys())
    m_cls = msgs['gd_msgs/EasyInt32']
    m_instance = m_cls()
    m_instance.data = '1'  # the type is incorrect
    buff = StringIO()
    try:
        m_instance.serialize(buff)
        assert False, 'This should have raised a genpy.SerializationError'
    except genpy.SerializationError:
        pass
    except Exception:
        assert False, 'This should have raised a genpy.SerializationError instead'
