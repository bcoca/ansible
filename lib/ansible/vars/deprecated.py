# Copyright (c) 2019 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.utils.display import Display

display = Display()


class DeprecatedVar(object):

    def __init__(self, var, deprecation):
        self._var = var
        self._deprecation = deprecation

    def _depr(self):
        display.deprecated(self._depecation)

    # override special cases that don't work generically
    def __getattribute__(self, name):
        self._depr()
        return getattr(object.__getattribute__(self, "_var"), name)

    def __delattr__(self, name):
        self._depr()
        delattr(object.__getattribute__(self, "_var"), name)

    def __setattr__(self, name, value):
        self._depr()
        setattr(object.__getattribute__(self, "_var"), name, value)

    def __nonzero__(self):
        self._depr()
        return bool(object.__getattribute__(self, "_var"))

    def __str__(self):
        self._depr()
        return str(object.__getattribute__(self, "_var"))

    def __repr__(self):
        self._depr()
        return repr(object.__getattribute__(self, "_var"))

    # special cases found on the interwebs' tubes
    _special_names = [
        '__abs__', '__add__', '__and__', '__call__', '__cmp__', '__coerce__',
        '__contains__', '__delitem__', '__delslice__', '__div__', '__divmod__',
        '__eq__', '__float__', '__floordiv__', '__ge__', '__getitem__',
        '__getslice__', '__gt__', '__hash__', '__hex__', '__iadd__', '__iand__',
        '__idiv__', '__idivmod__', '__ifloordiv__', '__ilshift__', '__imod__',
        '__imul__', '__int__', '__invert__', '__ior__', '__ipow__', '__irshift__',
        '__isub__', '__iter__', '__itruediv__', '__ixor__', '__le__', '__len__',
        '__long__', '__lshift__', '__lt__', '__mod__', '__mul__', '__ne__',
        '__neg__', '__oct__', '__or__', '__pos__', '__pow__', '__radd__',
        '__rand__', '__rdiv__', '__rdivmod__', '__reduce__', '__reduce_ex__',
        '__repr__', '__reversed__', '__rfloorfiv__', '__rlshift__', '__rmod__',
        '__rmul__', '__ror__', '__rpow__', '__rrshift__', '__rshift__', '__rsub__',
        '__rtruediv__', '__rxor__', '__setitem__', '__setslice__', '__sub__',
        '__truediv__', '__xor__', 'next',
    ]

    @classmethod
    def _create_var_proxy(cls, theclass):
        """creates a proxy for the given var"""

        def make_method(name):
            def method(self, *args, **kw):
                self._deprecated()
                return getattr(object.__getattribute__(self, "_var"), name)(*args, **kw)
            return method

        namespace = {}
        for name in cls._special_names:
            if hasattr(theclass, name):
                namespace[name] = make_method(name)
        return type("%s(%s)" % (cls.__name__, theclass.__name__), (cls,), namespace)

    def __new__(cls, var, *args, **kwargs):
        """
        creates a cached proxy instance of the `var` class and then sets up a reference to the var via this class.
        (var, *args, **kwargs) are passed to this class' __init__, so deriving classes can define and __init__ method of their own.
        note: _class_var_cache is unique per deriving class (each deriving class must hold its own cache)
        """
        try:
            cache = cls.__dict__["_class_var_cache"]
        except KeyError:
            cls._class_var_cache = cache = {}
        try:
            theclass = cache[var.__class__]
        except KeyError:
            cache[var.__class__] = theclass = cls._create_class_proxy(var.__class__)
        ins = object.__new__(theclass)
        theclass.__init__(ins, var, *args, **kwargs)
        return ins
