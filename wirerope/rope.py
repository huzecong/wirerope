""":mod:`wirerope.rope` --- Universal method/function wrapper.
==============================================================
"""
import six
from .callable import Callable
from .wire import descriptor_bind
from ._compat import functools


class RopeCore(object):

    def __init__(self, callable, rope):
        super(RopeCore, self).__init__()
        self.callable = callable
        self.rope = rope
        self.wire_class = rope.wire_class


class MethodRopeMixin(object):

    def __init__(self, *args, **kwargs):
        super(MethodRopeMixin, self).__init__(*args, **kwargs)
        assert not self.callable.is_barefunction

    def __get__(self, obj, type=None):
        cw = self.callable
        co = cw.wrapped_object
        owner, _ = descriptor_bind(co, obj, type)
        if owner is None:  # invalid binding but still wire it
            owner = obj if obj is not None else type
        wire_name_parts = ['__wire_', cw.wrapped_callable.__name__]
        if owner is type:
            wire_name_parts.extend(('_', type.__name__))
        wire_name = ''.join(wire_name_parts)
        wire = getattr(owner, wire_name, None)
        if wire is None:
            wire = self.wire_class(self, owner, (obj, type))
            setattr(owner, wire_name, wire)
        assert callable(wire.__func__)
        return wire


class PropertyRopeMixin(object):

    def __init__(self, *args, **kwargs):
        super(PropertyRopeMixin, self).__init__(*args, **kwargs)
        assert not self.callable.is_barefunction

    def __get__(self, obj, type=None):
        cw = self.callable
        co = cw.wrapped_object
        owner, _ = descriptor_bind(co, obj, type)
        if owner is None:  # invalid binding but still wire it
            owner = obj if obj is not None else type
        wire_name_parts = ['__wire_', cw.wrapped_callable.__name__]
        if owner is type:
            wire_name_parts.extend(('_', type.__name__))
        wire_name = ''.join(wire_name_parts)
        wire = getattr(owner, wire_name, None)
        if wire is None:
            wire = self.wire_class(self, owner, (obj, type))
            wire._bound_objects = (owner,)
            setattr(owner, wire_name, wire)

        return wire._on_property()  # requires property path


class FunctionRopeMixin(object):

    def __init__(self, *args, **kwargs):
        super(FunctionRopeMixin, self).__init__(*args, **kwargs)
        assert self.callable.is_barefunction
        self._wire = self.wire_class(self, None, None)

    def __getattr__(self, name):
        try:
            return self.__getattribute__(name)
        except AttributeError:
            pass
        return getattr(self._wire, name)


class CallableRopeMixin(object):

    def __init__(self, *args, **kwargs):
        super(CallableRopeMixin, self).__init__(*args, **kwargs)
        self.__call__ = functools.wraps(self.callable.wrapped_object)(self)

    def __call__(self, *args, **kwargs):
        return self._wire(*args, **kwargs)


class WireRope(object):

    def __init__(self, wire_class, core_class=RopeCore, rope_args=None):
        self.wire_class = wire_class
        self.method_rope = type(
            '_MethodRope', (MethodRopeMixin, core_class), {})
        self.property_rope = type(
            '_PropertyRope', (PropertyRopeMixin, core_class), {})
        self.function_rope = type(
            '_FunctionRope', (FunctionRopeMixin, core_class), {})
        self.callable_function_rope = type(
            '_CallableFunctionRope',
            (CallableRopeMixin, FunctionRopeMixin, core_class), {})
        for rope in (self, self.method_rope, self.property_rope,
                     self.function_rope, self.callable_function_rope):
            rope._args = rope_args

    def __call__(self, function):
        """Wrap a function/method definition.

        :return: Wrapper object. The return type is up to given callable is
                 function or method.
        """
        cw = Callable(function)
        if cw.is_barefunction:
            rope_class = self.callable_function_rope
            wire_class_call = self.wire_class.__call__
            if six.PY3:
                if wire_class_call.__qualname__ == 'type.__call__':
                    rope_class = self.function_rope
            else:
                # method-wrapper test for CPython2.7
                # im_class == type test for PyPy2.7
                if type(wire_class_call).__name__ == 'method-wrapper' or \
                        wire_class_call.im_class == type:
                    rope_class = self.function_rope
        elif cw.is_property:
            rope_class = self.property_rope
        else:
            rope_class = self.method_rope
        rope = rope_class(cw, rope=self)
        return rope
