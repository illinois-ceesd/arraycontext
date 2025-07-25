"""Testing for internal  utilities."""

# Do not add
# from __future__ import annotations
# to allow the non-string annotations below to work.


__copyright__ = "Copyright (C) 2021 University of Illinois Board of Trustees"

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

# The imports below ignore deprecation because we're testing behavior when
# deprecated types are used.

import logging
from typing import (  # noqa: UP035
    ClassVar,
    Optional,  # pyright: ignore[reportDeprecated]
    Tuple,  # pyright: ignore[reportDeprecated]
    cast,
)

import numpy as np
import pytest


logger = logging.getLogger(__name__)


# {{{ test_pt_actx_key_stringification_uniqueness

def test_pt_actx_key_stringification_uniqueness():
    from arraycontext.impl.pytato.utils import _ary_container_key_stringifier

    assert (_ary_container_key_stringifier(((3, 2), 3))
            != _ary_container_key_stringifier((3, (2, 3))))

    assert (_ary_container_key_stringifier(("tup", 3, "endtup"))
            != _ary_container_key_stringifier(((3,),)))

# }}}


# {{{ test_dataclass_array_container

def test_dataclass_array_container() -> None:
    from dataclasses import dataclass, field

    from arraycontext import Array, dataclass_array_container

    # {{{ optional fields

    @dataclass
    class ArrayContainerWithOptional:
        x: np.ndarray
        # Deliberately left as Optional to test compatibility.
        y: Optional[np.ndarray]  # noqa: UP045

    with pytest.raises(TypeError, match="Field 'y' union contains non-array"):
        # NOTE: cannot have wrapped annotations (here by `Optional`)
        dataclass_array_container(ArrayContainerWithOptional)

    # }}}

    # {{{ type annotations

    @dataclass
    class ArrayContainerWithTuple:
        x: Array
        # Deliberately left as Tuple to test compatibility.
        y: Tuple[Array, Array]  # noqa: UP006

    with pytest.raises(TypeError, match="Type annotation not supported on field 'y'"):
        dataclass_array_container(ArrayContainerWithTuple)

    @dataclass
    class ArrayContainerWithTupleAlt:
        x: Array
        y: tuple[Array, Array]

    with pytest.raises(TypeError, match="Type annotation not supported on field 'y'"):
        dataclass_array_container(ArrayContainerWithTupleAlt)

    # }}}

    # {{{ field(init=False)

    @dataclass
    class ArrayContainerWithInitFalse:
        x: np.ndarray
        y: np.ndarray = field(default_factory=lambda: np.zeros(42),
                              init=False, repr=False)

    with pytest.raises(ValueError, match="Field with 'init=False' not allowed"):
        # NOTE: init=False fields are not allowed
        dataclass_array_container(ArrayContainerWithInitFalse)

    # }}}

    # {{{ device arrays

    @dataclass
    class ArrayContainerWithArray:
        x: Array
        y: Array

    dataclass_array_container(ArrayContainerWithArray)

    # }}}

# }}}


# {{{ test_dataclass_container_unions

def test_dataclass_container_unions() -> None:
    from dataclasses import dataclass

    from arraycontext import Array, dataclass_array_container

    # {{{ union fields

    @dataclass
    class ArrayContainerWithUnion:
        x: np.ndarray
        y: np.ndarray | Array

    dataclass_array_container(ArrayContainerWithUnion)

    @dataclass
    class ArrayContainerWithUnionAlt:
        x: np.ndarray
        y: np.ndarray | Array

    dataclass_array_container(ArrayContainerWithUnionAlt)

    # }}}

    # {{{ non-container union

    @dataclass
    class ArrayContainerWithWrongUnion:
        x: np.ndarray
        y: np.ndarray | list[bool]

    with pytest.raises(TypeError, match="Field 'y' union contains non-array container"):
        # NOTE: bool is not an ArrayContainer, so y should fail
        dataclass_array_container(ArrayContainerWithWrongUnion)

    # }}}

    # {{{ optional union

    @dataclass
    class ArrayContainerWithOptionalUnion:
        x: np.ndarray
        y: np.ndarray | None

    with pytest.raises(TypeError, match="Field 'y' union contains non-array container"):
        # NOTE: None is not an ArrayContainer, so y should fail
        dataclass_array_container(ArrayContainerWithWrongUnion)

    # }}}


# }}}


# {{{ test_stringify_array_container_tree


def test_stringify_array_container_tree() -> None:
    from dataclasses import dataclass

    from arraycontext import (
        Array,
        dataclass_array_container,
        stringify_array_container_tree,
    )

    @dataclass_array_container
    @dataclass(frozen=True)
    class ArrayWrapper:
        ary: Array

    @dataclass_array_container
    @dataclass(frozen=True)
    class SomeContainer:
        points: Array
        radius: float
        centers: ArrayWrapper

    @dataclass_array_container
    @dataclass(frozen=True)
    class SomeOtherContainer:
        disk: SomeContainer
        circle: SomeContainer
        has_disk: bool
        norm_type: str
        extent: float

        __array_ufunc__: ClassVar[None] = None

    rng = np.random.default_rng(seed=42)
    a = ArrayWrapper(ary=cast("Array", rng.random(10)))
    d = SomeContainer(
              points=cast("Array", rng.random((2, 10))),
              radius=rng.random(),
              centers=a)
    c = SomeContainer(
              points=cast("Array", rng.random((2, 10))),
              radius=rng.random(),
              centers=a)
    ary = SomeOtherContainer(
        disk=d, circle=c,
        has_disk=True,
        norm_type="l2",
        extent=1)

    logger.info("\n%s", stringify_array_container_tree(ary))

# }}}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        exec(sys.argv[1])
    else:
        pytest.main([__file__])

# vim: fdm=marker
