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

"""Dynamic generation of deserializer."""

from __future__ import print_function

try:
    from cStringIO import StringIO  # Python 2.x
except ImportError:
    from io import StringIO  # Python 3.x

import atexit
import importlib
import os
import re
import shutil
import sys
import tempfile

import genmsg
import genmsg.gentools
import genmsg.msg_loader
from genmsg import MsgContext, MsgGenerationException

from . generator import msg_generator


def _generate_dynamic_specs(msg_context, specs, dep_msg):
    """
    Dynamically generate message specificition.

    :param dep_msg: text of dependent .msg definition, ``str``
    :returns: type name, message spec, ``str, MsgSpec``
    :raises: MsgGenerationException If dep_msg is improperly formatted
    """
    line1 = dep_msg.find('\n')
    msg_line = dep_msg[:line1]
    if not msg_line.startswith('MSG: '):
        raise MsgGenerationException("invalid input to generate_dynamic: dependent type is missing 'MSG:' type declaration header")
    dep_type = msg_line[5:].strip()
    dep_pkg, dep_base_type = genmsg.package_resource_name(dep_type)
    dep_spec = genmsg.msg_loader.load_msg_from_string(msg_context, dep_msg[line1+1:], dep_type)
    return dep_type, dep_spec


def _gen_dyn_name(pkg, base_type):
    """
    Modify pkg/base_type name so that it can safely co-exist with statically generated files.

    :returns: name to use for pkg/base_type for dynamically generated message class.
    @rtype: str
    """
    return '_%s__%s' % (pkg, base_type)


def _gen_dyn_modify_references(py_text, current_type, types, matched=()):
    """
    Modify the generated code to rewrite names such that the code can safely co-exist with messages of the same name.

    :param py_text: genmsg_py-generated Python source code, ``str``
    :param matched: types whose installed class is md5-identical to the bag
      definition; their aliased imports are kept so references bind to the
      installed class, ``collection of str``
    :returns: updated text, ``str``
    """
    for t in types:
        if t in matched:
            continue
        pkg, base_type = genmsg.package_resource_name(t)
        gen_name = _gen_dyn_name(pkg, base_type)
        alias = '%s_msg_%s' % (pkg, base_type)

        # Drop imports that would otherwise load the INSTALLED definition
        py_text = py_text.replace(
            'from %s.msg._%s import %s as %s' % (pkg, base_type, base_type, alias), '')
        # Rewrite aliased references to the local dynamically-generated class
        if alias in py_text:
            py_text = re.sub(r'(?<!\w)%s(?!\w)' % re.escape(alias), gen_name, py_text)

    pkg, base_type = genmsg.package_resource_name(current_type)
    gen_name = _gen_dyn_name(pkg, base_type)
    # - class declaration
    py_text = py_text.replace('class %s(' % base_type, 'class %s(' % gen_name)
    # - super() references for __init__
    py_text = py_text.replace('super(%s,' % base_type, 'super(%s,' % gen_name)
    # std_msgs/Header constructor references use a dotted path the aliased
    # import does not bind, so rewrite them either to the kept alias (md5
    # match) or to the local dynamically-generated class
    if 'std_msgs/Header' in matched:
        py_text = py_text.replace('std_msgs.msg._Header.Header', 'std_msgs_msg_Header')
    else:
        py_text = py_text.replace('std_msgs.msg._Header.Header', _gen_dyn_name('std_msgs', 'Header'))
    return py_text


def _installed_class_if_md5_match(msg_context, msg_type, spec):
    """
    Return the installed message class for msg_type if its md5 matches spec.

    A matching md5 proves the installed definition (including all nested
    types) is byte-identical to the definition embedded in the bag, so the
    installed class can be used directly. This preserves class identity with
    the rest of the process (isinstance checks, C++ bindings such as tf2).

    :returns: installed class, or None if not importable or definitions differ
    """
    pkg, base_type = genmsg.package_resource_name(msg_type)
    try:
        mod = importlib.import_module('%s.msg._%s' % (pkg, base_type))
        cls = getattr(mod, base_type)
    except Exception:
        return None
    try:
        if getattr(cls, '_md5sum', None) == genmsg.gentools.compute_md5(msg_context, spec):
            return cls
    except Exception:
        return None
    return None


def _generate_dynamic_source(core_type, msg_cat):
    """
    Build the rewritten dynamic module source for msg_cat .msg text.

    Types whose installed class is md5-identical to the bag definition are not
    generated; references to them bind to the installed class instead.

    :returns: module source, specs by type, installed classes by matched type,
      ``(str, dict, dict)``
    :raises: MsgGenerationException If dep_msg is improperly formatted
    """
    msg_context = MsgContext.create_default()

    # REP 100: pretty gross hack to deal with the fact that we moved
    # Header. Header is 'special' because it can be used w/o a package
    # name, so the lookup rules end up failing. We are committed to
    # never changing std_msgs/Header, so this is generally fine.
    msg_cat = msg_cat.replace('roslib/Header', 'std_msgs/Header')

    # separate msg_cat into the core message and dependencies
    splits = msg_cat.split('\n'+'='*80+'\n')
    core_msg = splits[0]
    deps_msgs = splits[1:]

    # create MsgSpec representations of .msg text
    specs = {core_type: genmsg.msg_loader.load_msg_from_string(msg_context, core_msg, core_type)}
    # - dependencies
    for dep_msg in deps_msgs:
        # dependencies require more handling to determine type name
        dep_type, dep_spec = _generate_dynamic_specs(msg_context, specs, dep_msg)
        specs[dep_type] = dep_spec

    # clear the message registration table and register loaded
    # types. The types have to be registered globally in order for
    # message generation of dependents to work correctly.
    msg_context = genmsg.msg_loader.MsgContext.create_default()
    search_path = {}  # no ability to dynamically load
    for t, spec in specs.items():
        msg_context.register(t, spec)

    # installed classes that provably match the bag definition are used as-is
    matched = {}
    for t, spec in specs.items():
        cls = _installed_class_if_md5_match(msg_context, t, spec)
        if cls is not None:
            matched[t] = cls

    # process actual MsgSpecs: we accumulate them into a single file,
    # rewriting the generated text as needed
    buff = StringIO()
    for t, spec in specs.items():
        if t in matched:
            continue
        # dynamically generate python message code
        for line in msg_generator(msg_context, spec, search_path):
            line = _gen_dyn_modify_references(line, t, list(specs.keys()), matched)
            buff.write(line + '\n')
    full_text = buff.getvalue()
    # Defer annotation evaluation: dependent types may be defined later in this module.
    full_text = 'from __future__ import annotations\n' + full_text
    return full_text, specs, matched


def generate_dynamic(core_type, msg_cat):
    """
    Dynamically generate message classes from msg_cat .msg text gendeps dump.

    This method modifies sys.path to include a temp file directory.
    :param core_type str: top-level ROS message type of concatenated .msg text
    :param msg_cat str: concatenation of full message text (output of gendeps --cat)
    :raises: MsgGenerationException If dep_msg is improperly formatted
    """
    full_text, specs, matched = _generate_dynamic_source(core_type, msg_cat)

    # every definition matches an installed class: nothing to generate
    if len(matched) == len(specs):
        return dict(matched)

    # Create a temporary directory
    tmp_dir = tempfile.mkdtemp(prefix='genpy_')

    # Afterwards, we are going to remove the directory so that the .pyc file gets cleaned up if it's still around
    atexit.register(shutil.rmtree, tmp_dir)

    # write the entire text to a file and import it (it will get deleted when tmp_dir goes - above)
    tmp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.py', dir=tmp_dir, delete=False)
    tmp_file.file.write(full_text)
    tmp_file.file.close()

    # import our temporary file as a python module, which requires modifying sys.path
    sys.path.append(os.path.dirname(tmp_file.name))

    # - strip the prefix to turn it into the python module name
    try:
        mod = __import__(os.path.basename(tmp_file.name)[:-3])
    except Exception:
        # TODOXXX:REMOVE
        with open(tmp_file.name) as f:
            text = f.read()
            with open('/tmp/foo', 'w') as f2:
                f2.write(text)
        raise

    # finally, retrieve the message classes from the dynamic module
    messages = {}
    for t in specs.keys():
        if t in matched:
            # installed class is md5-identical to the bag definition; use it
            # directly so class identity is preserved (isinstance, tf2, ...)
            messages[t] = matched[t]
            continue
        pkg, s_type = genmsg.package_resource_name(t)
        try:
            messages[t] = getattr(mod, _gen_dyn_name(pkg, s_type))
        except AttributeError:
            raise MsgGenerationException('cannot retrieve message class for %s/%s: %s' % (pkg, s_type, _gen_dyn_name(pkg, s_type)))
        messages[t]._spec = specs[t]

    return messages
