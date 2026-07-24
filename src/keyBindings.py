# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
import os
import sys

if sys.version_info[0] < 3:
    import ConfigParser
    parserModule = ConfigParser
else:
    import configparser
    parserModule = configparser


CONFIG_DIR = os.environ.get('XDG_CONFIG_HOME') or '~/.config'
KEY_BINDINGS_FILE = os.path.join(CONFIG_DIR, 'fpp', 'key_bindings')


class KeyBindings(object):

    bindings = []

    def __init__(self, keyBindingsFile=KEY_BINDINGS_FILE):
        """Returns configured key bindings, in the format [(key, command), ...].
        The ordering of the entries is not guaranteed, although it's irrelevant to the purpose.
        """
        configFilePath = os.path.expanduser(keyBindingsFile)
        parser = parserModule.ConfigParser()
        parser.read(configFilePath)

        # The `executePreconfiguredCommand` underlying APIs use `curses.getstr()`, which returns an
        # encoded string, and invoke `decode()` on it.
        # In Python 3/configparser, the parsed strings are already decoded, therefore don't support
        # this method anymore, so we convert them to encoded ones first.
        #
        if parser.has_section("bindings"):
            self.bindings = [(key, command.encode('utf-8'))
                             for key, command in parser.items("bindings")]
