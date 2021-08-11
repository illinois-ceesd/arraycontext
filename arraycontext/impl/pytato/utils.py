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


from typing import Any, Dict, Set, Tuple, Mapping
from pytato.array import SizeParam, Placeholder
from pytato.array import Array, DataWrapper
from pytato.transform import CopyMapper
from pytools import UniqueNameGenerator


class _DatawrapperToBoundPlaceholderMapper(CopyMapper):
    """
    Helper mapper for :func:`normalize_pt_expr`. Every
    :class:`pytato.DataWrapper` is replaced with a deterministic copy of
    :class:`Placeholder`.
    """
    def __init__(self) -> None:
        super().__init__()
        self.bound_arguments: Dict[str, Any] = {}
        self.vng = UniqueNameGenerator()
        self.seen_inputs: Set[str] = set()

    def map_data_wrapper(self, expr: DataWrapper) -> Array:
        if expr.name is not None:
            if expr.name in self.seen_inputs:
                raise ValueError("Got multiple inputs with the name"
                                 f"{expr.name} => Illegal.")
            self.seen_inputs.add(expr.name)

        # Normalizing names so that we more arrays can have the normalized DAG.
        name = self.vng("_actx_dw")
        self.bound_arguments[name] = expr.data
        return Placeholder(name=name,
                           shape=tuple(self.rec(s) if isinstance(s, Array) else s
                                       for s in expr.shape),
                           dtype=expr.dtype,
                           tags=expr.tags)

    def map_size_param(self, expr: SizeParam) -> Array:
        raise NotImplementedError

    def map_placeholder(self, expr: Placeholder) -> Array:
        raise ValueError("Placeholders cannot appear in"
                         " DatawrapperToBoundPlaceholderMapper.")


def _normalize_pt_expr(expr: Array) -> Tuple[Array,
                                            Mapping[str, Any]]:
    """
    Returns ``(normalized_expr, bound_arguments)``.  *normalized_expr* is a
    normalized form of *expr*, with all instances of
    :class:`pytato.DataWrapper` replaced with instances of :class:`Placeholder`
    named in a deterministic manner. The data corresponding to the placeholders
    in *normalized_expr* is recorded in the mapping *bound_arguments*.
    Deterministic naming of placeholders permits more effective caching of
    equivalent graphs.
    """
    normalize_mapper = _DatawrapperToBoundPlaceholderMapper()
    normalized_expr = normalize_mapper(expr)
    return normalized_expr, normalize_mapper.bound_arguments