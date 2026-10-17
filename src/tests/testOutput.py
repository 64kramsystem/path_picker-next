# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
from __future__ import print_function
import stateFiles
import output
import processInput

import os
import pty
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, '../')


class LineObjForTest(object):

    def __init__(self, path, lineNum=0, resolvable=True, originalLine=None):
        self.path = path
        self.lineNum = lineNum
        self.resolvable = resolvable
        self.originalLine = originalLine or path

    def getPath(self):
        return self.path

    def getLineNum(self):
        return self.lineNum

    def getOriginalLine(self):
        return self.originalLine

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

    def testSelectExtensionlessFileFromTerminalOutput(self):
        fileName = 'install-windows-11-25h2-vm-ai_finishing'
        with open(os.path.join(self.fppDir, fileName), 'w'):
            pass
        transcript = '''~/code/system_install_scripts(main)⚠️ $ g sn
commit 5bd4e12 (HEAD -> main, origin/main, origin/HEAD)
Author: Saverio Miroddi <saverio.pub2@gmail.com>
Date:   Sat Oct 17 17:10:24 2026 +0200

    Shorten the Windows VM finishing prompt

M  %s
M  missing-extensionless-file
~/code/system_install_scripts(main)⚠️ $
''' % fileName
        env = dict(os.environ, FPP_DIR=os.path.join(self.fppDir, 'cache'),
                   TERM='xterm-256color', LINES='24', COLUMNS='120')
        fpp = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..', 'fpp'))
        master, slave = pty.openpty()
        terminalOutput = []

        def drainTerminal():
            while True:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    return
                if not chunk:
                    return
                terminalOutput.append(chunk)

        reader = threading.Thread(target=drainTerminal, daemon=True)
        reader.start()
        try:
            with subprocess.Popen(
                    [fpp, '--non-interactive', '--execute-keys', 'END', 'ENTER',
                     '--command', 'printf "%s\\n" $F > selected'],
                    cwd=self.fppDir, env=env, stdin=subprocess.PIPE,
                    stdout=slave, stderr=slave) as proc:
                try:
                    proc.communicate(transcript.encode('utf-8'), timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                    self.fail('PathPicker did not finish selecting the file')
            self.assertEqual(0, proc.returncode)
        finally:
            os.close(slave)
            reader.join(timeout=2)
            os.close(master)

        selected = os.path.join(self.fppDir, 'selected')
        self.assertTrue(os.path.isfile(selected),
                        b''.join(terminalOutput).decode('utf-8', 'replace'))
        with open(selected) as result:
            self.assertEqual('./' + fileName + '\n', result.read())

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

    def testExecPreconfiguredSCommandResumesCodexSession(self):
        sessionId = '019f94b0-470f-74f2-8b1d-42f298d1d559'
        lineObj = LineObjForTest(
            sessionId,
            originalLine=('run codex resume, then select foo bar (%s)' %
                          sessionId))
        output.execPreconfiguredCommand('s', 'code -g', [lineObj])
        contents = self.getOutput()
        self.assertIn("cod '%s'" % sessionId, contents)
        self.assertNotIn('code -g', contents)

    def testExecPreconfiguredSCommandResumesClaudeSession(self):
        sessionId = '019c8bbd-0f81-77a2-b170-76a70ab513e3'
        lineObj = LineObjForTest(
            sessionId,
            originalLine='claude --resume %s' % sessionId)
        output.execPreconfiguredCommand('s', 'code -g', [lineObj])
        contents = self.getOutput()
        self.assertIn("cla '%s'" % sessionId, contents)
        self.assertNotIn('code -g', contents)

    def testExecPreconfiguredSCommandResumesCodexFromMultilineFooter(self):
        sessionId = '01a08031-f701-7380-adc3-a651a75a4da3'
        lines = [
            'To continue this session, run:\n',
            '  codex resume %s\n' % sessionId,
            'Or run codex resume and select Assess palware fork.\n',
        ]
        lineObj = processInput.getLineObjsFromLines(
            lines, validateFileExists=True)[1]
        self.assertEqual(sessionId, lineObj.getPath())
        self.assertEqual(sessionId, lines[1][lineObj.start:lineObj.end])
        output.execPreconfiguredCommand('s', 'code -g', [lineObj])
        contents = self.getOutput()
        self.assertIn("cod '%s'" % sessionId, contents)
        self.assertNotIn('code -g', contents)

    def testExecPreconfiguredSCommandUsesConfiguredCommandForFile(self):
        lineObj = LineObjForTest(
            'src/output.py', originalLine='src/output.py:42')
        output.execPreconfiguredCommand('s', 'code -g', [lineObj])
        self.assertIn("code -g 'src/output.py'", self.getOutput())

    def testExecPreconfiguredSCommandUsesHighlightedFileFromSessionLine(self):
        sessionId = '019f94b0-470f-74f2-8b1d-42f298d1d559'
        line = ('run codex resume, then select ~/src/output.py (%s)' %
                sessionId)
        lineObj = processInput.getLineObjsFromLines(
            [line], validateFileExists=False)[0]
        output.execPreconfiguredCommand('s', 'code -g', [lineObj])
        contents = self.getOutput()
        self.assertIn("code -g '%s'" %
                      os.path.expanduser('~/src/output.py'), contents)
        self.assertNotIn('cod ', contents)

    def testExecPreconfiguredSCommandRejectsMultipleSelections(self):
        lineObjs = [LineObjForTest('src/output.py'),
                    LineObjForTest('src/parse.py')]
        output.execPreconfiguredCommand('s', 'code -g', lineObjs)
        contents = self.getOutput()
        self.assertIn('s accepts only one selected entry.', contents)
        self.assertIn('exit 1', contents)
        self.assertNotIn('code -g', contents)

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
