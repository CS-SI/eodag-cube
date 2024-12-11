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
from __future__ import annotations

import logging
from collections import UserDict
from typing import Union

import xarray as xr

logger = logging.getLogger("eodag-cube.types")


class XarrayDict(UserDict[str, Union[xr.Dataset, UserDict[str, xr.Dataset]]]):
    """
    Dictionnary which keys are file paths and values are xarray Datasets.
    """

    def _format_dims(self, ds):
        return ", ".join(f"{key}: {value}" for key, value in ds.sizes.items())

    def _repr_html_(self):
        title = self.__class__.__name__
        count = len(self)
        header = f"{title} ({count})"
        header_underline = "-" * len(header)

        lines = ["<pre>", header, header_underline]

        for key, ds in self.items():
            formatted_dims = self._format_dims(ds)
            line = f"> {key} : xarray.Dataset ({formatted_dims})"
            lines.append(line)

        lines.append("</pre>")

        return "\n".join(lines)

