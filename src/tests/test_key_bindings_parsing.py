# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
import os
import tempfile
import unittest

from pathpicker.key_bindings import KEY_BINDINGS_FILE, read_key_bindings
from tests.lib.key_bindings import (
    KEY_BINDINGS_FOR_TEST,
    KEY_BINDINGS_FOR_TEST_CONFIG_CONTENT,
)


class TestKeyBindingsParser(unittest.TestCase):
    def test_default_file_is_in_xdg_config_dir(self) -> None:
        expected_dir = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
        self.assertEqual(os.path.join(expected_dir, "fpp", ".fpp.keys"), KEY_BINDINGS_FILE)

    def test_ignore_non_existing_configuration_file(self) -> None:
        file = tempfile.NamedTemporaryFile(delete=True)
        file.close()

        bindings = read_key_bindings(file.name)

        self.assertEqual(
            bindings,
            [],
            (
                "The parser did not return an empty list, "
                f"when initialized with a non-existent file: {bindings}"
            ),
        )

    def test_standard_parsing(self) -> None:
        file = tempfile.NamedTemporaryFile(mode="wt", delete=False)
        file.write(KEY_BINDINGS_FOR_TEST_CONFIG_CONTENT)
        file.close()

        bindings = read_key_bindings(file.name)

        actual_result = sorted(bindings)
        expected_result = KEY_BINDINGS_FOR_TEST

        self.assertEqual(
            actual_result,
            expected_result,
            (
                "The parser did not properly parse the test file\n\n"
                f'Expected:"{expected_result}"\nActual  :"{actual_result}"'
            ),
        )


if __name__ == "__main__":
    unittest.main()
