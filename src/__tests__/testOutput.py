# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
from __future__ import print_function
import stateFiles
import output

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, '../')


class LineObjForTest(object):

    def __init__(self, path, lineNum=0, resolvable=True):
        self.path = path
        self.lineNum = lineNum
        self.resolvable = resolvable

    def getPath(self):
        return self.path

    def getLineNum(self):
        return self.lineNum

    def getDir(self):
        return os.path.dirname(self.path)

    def isResolvable(self):
        return self.resolvable

    def isGitAbbreviatedPath(self):
        return self.path.startswith('.../')


class TestOutput(unittest.TestCase):

    def setUp(self):
        self.fppDir = tempfile.mkdtemp()
        self.origFppDir = stateFiles.FPP_DIR
        stateFiles.FPP_DIR = self.fppDir
        self.origShell = os.environ.get('SHELL')
        os.environ['SHELL'] = '/bin/bash'

    def tearDown(self):
        stateFiles.FPP_DIR = self.origFppDir
        if self.origShell is None:
            del os.environ['SHELL']
        else:
            os.environ['SHELL'] = self.origShell
        shutil.rmtree(self.fppDir)

    def getOutput(self):
        file = open(stateFiles.getScriptOutputFilePath())
        contents = file.read()
        file.close()
        return contents

    def testComposeFileCommandAppendsPaths(self):
        lineObjs = [LineObjForTest('a/b.py'), LineObjForTest('c/d.py')]
        command = output.composeFileCommand('cat', lineObjs)
        self.assertEqual("cat 'a/b.py' 'c/d.py'", command)

    def testComposeFileCommandSubstitutesToken(self):
        lineObjs = [LineObjForTest('a/b.py')]
        command = output.composeFileCommand('git add $F -v', lineObjs)
        self.assertEqual("git add 'a/b.py' -v", command)

    def testComposeCdCommand(self):
        lineObjs = [LineObjForTest('a/b/c.py')]
        command = output.composeCommand('cd', lineObjs)
        self.assertEqual(
            'echo "%s" > ~/.dircopy' % os.path.abspath('a/b'), command)

    def testExecComposedCommand(self):
        output.execComposedCommand('cat', [LineObjForTest('a/b.py')])
        contents = self.getOutput()
        self.assertIn('echo "executing command:"', contents)
        self.assertIn("cat 'a/b.py'", contents)
        self.assertIn('exit $?;', contents)

    def testExecComposedCommandQuiet(self):
        output.execComposedCommand('@quiet cat', [LineObjForTest('a/b.py')])
        contents = self.getOutput()
        self.assertNotIn('echo "executing command:"', contents)
        self.assertIn("cat 'a/b.py'", contents)
        self.assertIn('exit $?;', contents)

    def testExecComposedCommandWarnsOnInvalidFiles(self):
        output.execComposedCommand(
            'cat', [LineObjForTest('a/b.py', resolvable=False)])
        contents = self.getOutput()
        self.assertIn(output.INVALID_FILE_WARNING, contents)
        self.assertIn(output.CONTINUE_WARNING, contents)

    def testEditFiles(self):
        os.environ['FPP_EDITOR'] = 'joe'
        try:
            output.editFiles([LineObjForTest('a/b.py', lineNum=3),
                              LineObjForTest('c/d.py')])
        finally:
            del os.environ['FPP_EDITOR']
        contents = self.getOutput()
        self.assertIn("joe  +3 'a/b.py' 'c/d.py'", contents)
        self.assertIn('exit $?;', contents)

    def testAppendExitUsesShellStatusVariable(self):
        os.environ['SHELL'] = '/usr/bin/fish'
        output.appendExit()
        self.assertIn('exit $status;', self.getOutput())


if __name__ == '__main__':
    unittest.main()
