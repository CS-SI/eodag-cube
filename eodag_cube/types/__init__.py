# -*- coding: utf-8 -*-
# Copyright 2024, CS GROUP - France, http://www.c-s.fr
#
# This file is part of EODAG project
#     https://www.github.com/CS-SI/EODAG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""EODAG-Cube types package"""

from __future__ import annotations

import logging
from collections import UserDict
from typing import TYPE_CHECKING, Any

import xarray as xr

if TYPE_CHECKING:
    from fsspec.core import OpenFile

logger = logging.getLogger("eodag-cube.types")


class XarrayDict(UserDict[str, xr.Dataset]):
    """
    Dictionnary that stores as values independant :class:`xarray.Dataset` having various
    dimensions.

    Example
    -------

    >>> import xarray
    >>> XarrayDict({
    ...     "foo": xarray.Dataset.from_dict(
    ...         {
    ...             "x": {"dims": ("x"), "data": [0, 1]},
    ...             "a": {"dims": ("x"), "data": [10, 20]}
    ...         }
    ...     ),
    ...     "bar": xarray.Dataset.from_dict(
    ...         {
    ...             "y": {"dims": ("y"), "data": [0, 1, 2]},
    ...             "b": {"dims": ("y"), "data": [10, 20, 30]}
    ...         }
    ...     )
    ... })
    <XarrayDict> (2)
    {'foo': <xarray.Dataset> (x: 2) Size: 32B,
    'bar': <xarray.Dataset> (y: 3) Size: 48B}
    """

    _files: dict[str, OpenFile] = {}

    def __enter__(self):
        return self

    def __exit__(self, *args: Any):
        self.close()

    def _format_dims(self, ds):
        return ", ".join(f"{key}: {value}" for key, value in ds.sizes.items())

    def _formatted_title(self, v):
        return (
            str(v)
            .split("\n")[0]
            .replace("<", "")
            .replace(
                ">",
                f"&ensp;<span style='color: black'>({self._format_dims(v)})</span>&ensp;",
            )
        )

    def _formatted_title_raw(self, v):
        return (
            str(v)
            .split("\n")[0]
            .replace(
                ">",
                f"> ({self._format_dims(v)})",
            )
        )

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__}> ({len(self)})\n"
            + "{"
            + ",\n".join([f"'{k}': {self._formatted_title_raw(v)}" for k, v in self.items()])
            + "}"
        )

    def _repr_html_(self, embedded: bool = False) -> str:
        thead = (
            f"""<thead><tr><td style='text-align: left; color: grey;'>
                {type(self).__name__}&ensp;({len(self)})
            """
            + "</td></tr></thead>"
            if not embedded
            else ""
        )
        tr_style = "style='background-color: transparent;'" if embedded else ""
        return (
            f"<table>{thead}<tbody>"
            + "".join(
                [
                    f"""<tr {tr_style}><td style='text-align: left;'>
                        <details><summary style='color: grey;'>
                        <span style='color: black'>'{k}'</span>:&ensp;
                        {self._formatted_title(v)}
                    </summary>
                        {v._repr_html_()}
                    </details>
                    </td></tr>
                    """
                    for k, v in self.items()
                ]
            )
            + "</tbody></table>"
        )

    def close(self) -> None:
        """Close all datasets and associated file objects"""
        for k, ds in self.items():
            ds.close()
            if k in self._files:
                self._files[k].close()

    def sort(self) -> None:
        """In place sort items by keys"""
        self.data = dict(sorted(self.data.items()))
