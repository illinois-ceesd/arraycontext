from __future__ import annotations


__copyright__ = """
Copyright (C) 2021 University of Illinois Board of Trustees
"""

__license__ = """
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""
from functools import partial, reduce
from typing import TYPE_CHECKING, cast

import numpy as np
from typing_extensions import override

import jax.numpy as jnp

from arraycontext.container import (
    NotAnArrayContainerError,
    serialize_container,
)
from arraycontext.container.traversal import (
    rec_map_container,
    rec_map_reduce_array_container,
    rec_multimap_array_container,
)
from arraycontext.fake_numpy import BaseFakeNumpyLinalgNamespace, BaseFakeNumpyNamespace
from arraycontext.typing import is_scalar_like


if TYPE_CHECKING:
    from numpy.typing import DTypeLike

    from pymbolic import Scalar

    from arraycontext.impl.jax import EagerJAXArrayContext
    from arraycontext.typing import (
        Array,
        ArrayOrContainerOrScalar,
        ArrayOrScalar,
    )


class EagerJAXFakeNumpyLinalgNamespace(BaseFakeNumpyLinalgNamespace):
    # Everything is implemented in the base class for now.
    pass


class EagerJAXFakeNumpyNamespace(BaseFakeNumpyNamespace):
    """
    A :mod:`numpy` mimic for :class:`~arraycontext.EagerJAXArrayContext`.
    """
    _array_context: EagerJAXArrayContext

    @override
    def _get_fake_numpy_linalg_namespace(self):
        return EagerJAXFakeNumpyLinalgNamespace(self._array_context)

    def __getattr__(self, name: str):
        return partial(rec_multimap_array_container, getattr(jnp, name))

    # NOTE: the order of these follows the order in numpy docs
    # NOTE: when adding a function here, also add it to `array_context.rst` docs!

    # {{{ array creation routines

    @override
    def zeros(self, shape: int | tuple[int, ...], dtype: DTypeLike) -> Array:
        return cast("Array", cast("object", jnp.zeros(shape=shape, dtype=dtype)))

    @override
    def _full_like_array(self,
                ary: Array,
                fill_value: Scalar
            ) -> Array:
        return cast("Array", cast("object", jnp.full_like(ary, fill_value)))

    # }}}

    # {{{ array manipulation routies

    def ravel(self, a: ArrayOrContainerOrScalar, order="C"):
        """
        .. warning::

            Since :func:`jax.numpy.reshape` does not support orders `A`` and
            ``K``, in such cases we fallback to using ``order = C``.
        """
        if order in "AK":
            from warnings import warn
            warn(f"ravel with order='{order}' not supported by JAX,"
                 " using order=C.", stacklevel=1)
            order = "C"

        def inner_ravel(ary: ArrayOrScalar) -> ArrayOrScalar:
            if is_scalar_like(ary):
                return ary
            else:
                assert isinstance(ary, jnp.ndarray)
                return cast("Array", cast("object", jnp.ravel(ary, order)))

        return rec_map_container(inner_ravel, a)

    def broadcast_to(self, array: ArrayOrContainerOrScalar, shape: tuple[int, ...]):
        def inner_bcast(ary: ArrayOrScalar) -> ArrayOrScalar:
            if is_scalar_like(ary):
                return ary
            else:
                assert isinstance(ary, np.ndarray)
                return cast("Array", cast("object", jnp.broadcast_to(ary, shape)))

        return rec_map_container(inner_bcast, array)

    def concatenate(self, arrays, axis=0):
        return rec_multimap_array_container(jnp.concatenate, arrays, axis)

    def stack(self, arrays, axis=0):
        return rec_multimap_array_container(
            lambda *args: jnp.stack(arrays=args, axis=axis),
            *arrays)

    # }}}

    # {{{ linear algebra

    def vdot(self, x, y, dtype=None):
        from arraycontext import rec_multimap_reduce_array_container

        def _rec_vdot(ary1, ary2):
            common_dtype = np.result_type(ary1, ary2)
            if dtype not in (None, common_dtype):
                raise NotImplementedError(
                    f"{type(self).__name__} cannot take dtype in vdot.")

            return jnp.vdot(ary1, ary2)

        return rec_multimap_reduce_array_container(sum, _rec_vdot, x, y)

    # }}}

    # {{{ logic functions

    def all(self, a):
        return rec_map_reduce_array_container(
            partial(reduce, jnp.logical_and), jnp.all, a)

    def any(self, a):
        return rec_map_reduce_array_container(
            partial(reduce, jnp.logical_or), jnp.any, a)

    @override
    def array_equal(self,
                a: ArrayOrContainerOrScalar,
                b: ArrayOrContainerOrScalar
            ) -> Array:
        actx = self._array_context

        # NOTE: not all backends support `bool` properly, so use `int8` instead
        true_ary = actx.from_numpy(np.int8(True))
        false_ary = actx.from_numpy(np.int8(False))

        def rec_equal(x, y):
            if type(x) is not type(y):
                return false_ary

            try:
                serialized_x = serialize_container(x)
                serialized_y = serialize_container(y)
            except NotAnArrayContainerError:
                if x.shape != y.shape:
                    return false_ary
                else:
                    return jnp.all(jnp.equal(x, y))
            else:
                if len(serialized_x) != len(serialized_y):
                    return false_ary
                return reduce(
                        jnp.logical_and,
                        [(true_ary if kx_i == ky_i else false_ary)
                            and rec_equal(x_i, y_i)
                            for (kx_i, x_i), (ky_i, y_i)
                            in zip(serialized_x, serialized_y, strict=True)],
                        true_ary)

        return rec_equal(a, b)

    # }}}

    # {{{ mathematical functions

    @override
    def sum(self,
                a: ArrayOrContainerOrScalar,
                axis: int | tuple[int, ...] | None = None,
                dtype: DTypeLike = None,
            ) -> ArrayOrScalar:
        return rec_map_reduce_array_container(
            sum,
            partial(jnp.sum, axis=axis, dtype=dtype),
            a)

    @override
    def min(self,
                a: ArrayOrContainerOrScalar,
                axis: int | tuple[int, ...] | None = None,
            ) -> ArrayOrScalar:
        return rec_map_reduce_array_container(
                partial(reduce, jnp.minimum), partial(jnp.amin, axis=axis), a)

    amin = min

    @override
    def max(self,
                a: ArrayOrContainerOrScalar,
                axis: int | tuple[int, ...] | None = None,
            ) -> ArrayOrScalar:
        return rec_map_reduce_array_container(
                partial(reduce, jnp.maximum), partial(jnp.amax, axis=axis), a)

    amax = max

    # }}}

    # {{{ sorting, searching and counting

    def where(self, criterion, then, else_):
        return rec_multimap_array_container(jnp.where, criterion, then, else_)

    # }}}
