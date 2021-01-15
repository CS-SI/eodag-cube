# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, http://www.c-s.fr
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

import os
import unittest
from contextlib import contextmanager

from click.testing import CliRunner
from faker import Faker

from tests import TEST_RESOURCES_PATH
from tests.context import eodag
from tests.utils import mock


class TestEodagCli(unittest.TestCase):
    @contextmanager
    def user_conf(self, conf_file="user_conf.yml", content=b"key: to unused conf"):
        """Utility method"""
        with self.runner.isolated_filesystem():
            with open(conf_file, "wb") as fd:
                fd.write(
                    content if isinstance(content, bytes) else content.encode("utf-8")
                )
            yield conf_file

    def setUp(self):
        self.runner = CliRunner()
        self.faker = Faker()

    @mock.patch("eodag_cube.rpc.server.EODAGRPCServer", autospec=True)
    def test_eodag_serve_rpc_ok(self, rpc_server):
        """Calling eodag serve-rpc serve eodag methods as RPC server"""
        config_path = os.path.join(TEST_RESOURCES_PATH, "file_config_override.yml")
        self.runner.invoke(eodag, ["serve-rpc", "-f", config_path])
        rpc_server.assert_called_once_with("localhost", 50051, config_path)
        rpc_server.return_value.serve.assert_any_call()
        self.assertEqual(rpc_server.return_value.serve.call_count, 1)
