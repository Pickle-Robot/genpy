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

################################################################################
# Primitive type handling for ROS builtin types

SIMPLE_TYPES_DICT = {  # see python module struct
    'int8': 'b',
    'uint8': 'B',
    # Python 2.6 adds in '?' for C99 _Bool, which appears equivalent to an uint8,
    # thus, we use uint8
    'bool': 'B',
    'int16': 'h',
    'uint16': 'H',
    'int32': 'i',
    'uint32': 'I',
    'int64': 'q',
    'uint64': 'Q',
    'float32': 'f',
    'float64': 'd',
    # deprecated
    'char': 'B',  # unsigned
    'byte': 'b',  # signed
    }

# Simple types are primitives with fixed-serialization length
SIMPLE_TYPES = list(SIMPLE_TYPES_DICT.keys())  # py3k

# REF https://docs.python.org/3/library/struct.html#format-characters
# Map of simple ros message tpyes to python types
PY_TYPE_STRINGS = {
    'int8': 'int',
    'uint8': 'bytes',
    'byte': 'bytes',
    'int16': 'int',
    'uint16': 'int',
    'int32': 'int',
    'uint32': 'int', 
    'int64': 'int',
    'uint64': 'int',
    'float32': 'float',
    'float64': 'float',
    'string': 'str',
    'bool': 'bool',
    'char': 'bytes',
    'time': 'genpy.Time', # See: https://github.com/Pickle-Robot/genmsg/blob/b3c24ea4a75ac494e4f94bf88e8838c71f4280a5/src/genmsg/msgs.py#L326
    'duration': 'genpy.Duration'
}



def is_simple(type_):
    """
    Check if a type is a 'simple' type.

    :returns: ``True`` if type is a 'simple' type, i.e. is of
      fixed/known serialization length. This is effectively all primitive
      types except for string, ``bool``
    """
    return type_ in SIMPLE_TYPES
