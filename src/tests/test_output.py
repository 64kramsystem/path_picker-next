# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
import os
import pty
import shutil
import subprocess
import tempfile
import threading
import unittest

import process_input
from pathpicker import output, state_files


class LineObjForTest(object):

    def __init__(self, path, line_num=0, resolvable=True, original_line=None):
        self.path = path
        self.line_num = line_num
        self.resolvable = resolvable
        self.original_line = original_line or path

    def get_path(self):
        return self.path

    def get_line_num(self):
        return self.line_num

    def get_original_line(self):
        return self.original_line

    def get_dir(self):
        return os.path.dirname(self.path)

    def is_resolvable(self):
        return self.resolvable

    def is_git_abbreviated_path(self):
        return self.path.startswith(".../")


class TestOutput(unittest.TestCase):

    def setUp(self):
        self.fpp_dir = tempfile.mkdtemp()
        self.orig_fpp_dir = state_files.FPP_DIR
        state_files.FPP_DIR = self.fpp_dir
        self.orig_shell = os.environ.get("SHELL")
        os.environ["SHELL"] = "/bin/bash"

    def tearDown(self):
        state_files.FPP_DIR = self.orig_fpp_dir
        if self.orig_shell is None:
            del os.environ["SHELL"]
        else:
            os.environ["SHELL"] = self.orig_shell
        shutil.rmtree(self.fpp_dir)

    def get_output(self):
        file = open(state_files.get_script_output_file_path())
        contents = file.read()
        file.close()
        return contents

    def test_compose_file_command_appends_paths(self):
        line_objs = [LineObjForTest("a/b.py"), LineObjForTest("c/d.py")]
        command = output.compose_file_command("cat", line_objs)
        self.assertEqual("cat 'a/b.py' 'c/d.py'", command)

    def test_select_extensionless_file_from_terminal_output(self):
        file_name = "install-windows-11-25h2-vm-ai_finishing"
        with open(os.path.join(self.fpp_dir, file_name), "w"):
            pass
        transcript = """~/code/system_install_scripts(main)⚠️ $ g sn
commit 5bd4e12 (HEAD -> main, origin/main, origin/HEAD)
Author: Saverio Miroddi <saverio.pub2@gmail.com>
Date:   Sat Oct 17 17:10:24 2026 +0200

    Shorten the Windows VM finishing prompt

M  %s
M  missing-extensionless-file
~/code/system_install_scripts(main)⚠️ $
""" % file_name
        env = dict(
            os.environ,
            FPP_DIR=os.path.join(self.fpp_dir, "cache"),
            TERM="xterm-256color",
            LINES="24",
            COLUMNS="120",
        )
        fpp = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "fpp")
        )
        master, slave = pty.openpty()
        terminal_output = []

        def drain_terminal():
            while True:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    return
                if not chunk:
                    return
                terminal_output.append(chunk)

        reader = threading.Thread(target=drain_terminal, daemon=True)
        reader.start()
        try:
            with subprocess.Popen(
                [
                    fpp,
                    "--non-interactive",
                    "--execute-keys",
                    "END",
                    "ENTER",
                    "--command",
                    'printf "%s\\n" $F > selected',
                ],
                cwd=self.fpp_dir,
                env=env,
                stdin=subprocess.PIPE,
                stdout=slave,
                stderr=slave,
            ) as proc:
                try:
                    proc.communicate(transcript.encode("utf-8"), timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                    self.fail("PathPicker did not finish selecting the file")
            self.assertEqual(0, proc.returncode)
        finally:
            os.close(slave)
            reader.join(timeout=2)
            os.close(master)

        selected = os.path.join(self.fpp_dir, "selected")
        self.assertTrue(
            os.path.isfile(selected),
            b"".join(terminal_output).decode("utf-8", "replace"),
        )
        with open(selected) as result:
            self.assertEqual("./" + file_name + "\n", result.read())

    def test_compose_file_command_substitutes_token(self):
        line_objs = [LineObjForTest("a/b.py")]
        command = output.compose_file_command("git add $F -v", line_objs)
        self.assertEqual("git add 'a/b.py' -v", command)

    def test_compose_cd_command(self):
        line_objs = [LineObjForTest("a/b/c.py")]
        command = output.compose_command("cd", line_objs)
        self.assertEqual('echo "%s" > ~/.dircopy' % os.path.abspath("a/b"), command)

    def test_exec_composed_command(self):
        output.exec_composed_command("cat", [LineObjForTest("a/b.py")])
        contents = self.get_output()
        self.assertIn('echo "executing command:"', contents)
        self.assertIn("cat 'a/b.py'", contents)
        self.assertIn("exit $?;", contents)

    def test_exec_composed_command_quiet(self):
        output.exec_composed_command("@quiet cat", [LineObjForTest("a/b.py")])
        contents = self.get_output()
        self.assertNotIn('echo "executing command:"', contents)
        self.assertIn("cat 'a/b.py'", contents)
        self.assertIn("exit $?;", contents)

    def test_exec_preconfigured_s_command_resumes_codex_session(self):
        session_id = "019f94b0-470f-74f2-8b1d-42f298d1d559"
        line_obj = LineObjForTest(
            session_id,
            original_line=("run codex resume, then select foo bar (%s)" % session_id),
        )
        output.exec_preconfigured_command("s", "code -g", [line_obj])
        contents = self.get_output()
        self.assertIn("cod '%s'" % session_id, contents)
        self.assertNotIn("code -g", contents)

    def test_exec_preconfigured_s_command_resumes_claude_session(self):
        session_id = "019c8bbd-0f81-77a2-b170-76a70ab513e3"
        line_obj = LineObjForTest(
            session_id, original_line="claude --resume %s" % session_id
        )
        output.exec_preconfigured_command("s", "code -g", [line_obj])
        contents = self.get_output()
        self.assertIn("cla '%s'" % session_id, contents)
        self.assertNotIn("code -g", contents)

    def test_exec_preconfigured_s_command_resumes_codex_from_multiline_footer(self):
        session_id = "01a08031-f701-7380-adc3-a651a75a4da3"
        lines = [
            "To continue this session, run:\n",
            "  codex resume %s\n" % session_id,
            "Or run codex resume and select Assess palware fork.\n",
        ]
        line_obj = process_input.get_line_objs_from_lines(
            lines, validate_file_exists=True
        )[1]
        self.assertEqual(session_id, line_obj.get_path())
        self.assertEqual(session_id, lines[1][line_obj.start : line_obj.end])
        output.exec_preconfigured_command("s", "code -g", [line_obj])
        contents = self.get_output()
        self.assertIn("cod '%s'" % session_id, contents)
        self.assertNotIn("code -g", contents)

    def test_exec_preconfigured_s_command_uses_configured_command_for_file(self):
        line_obj = LineObjForTest("src/output.py", original_line="src/output.py:42")
        output.exec_preconfigured_command("s", "code -g", [line_obj])
        self.assertIn("code -g 'src/output.py'", self.get_output())

    def test_exec_preconfigured_s_command_uses_highlighted_file_from_session_line(self):
        session_id = "019f94b0-470f-74f2-8b1d-42f298d1d559"
        line = "run codex resume, then select ~/src/output.py (%s)" % session_id
        line_obj = process_input.get_line_objs_from_lines(
            [line], validate_file_exists=False
        )[0]
        output.exec_preconfigured_command("s", "code -g", [line_obj])
        contents = self.get_output()
        self.assertIn("code -g '%s'" % os.path.expanduser("~/src/output.py"), contents)
        self.assertNotIn("cod ", contents)

    def test_exec_preconfigured_s_command_rejects_multiple_selections(self):
        line_objs = [LineObjForTest("src/output.py"), LineObjForTest("src/parse.py")]
        output.exec_preconfigured_command("s", "code -g", line_objs)
        contents = self.get_output()
        self.assertIn("s accepts only one selected entry.", contents)
        self.assertIn("exit 1", contents)
        self.assertNotIn("code -g", contents)

    def test_exec_composed_command_warns_on_invalid_files(self):
        output.exec_composed_command(
            "cat", [LineObjForTest("a/b.py", resolvable=False)]
        )
        contents = self.get_output()
        self.assertIn(output.INVALID_FILE_WARNING, contents)
        self.assertIn(output.CONTINUE_WARNING, contents)

    def test_edit_files(self):
        os.environ["FPP_EDITOR"] = "joe"
        try:
            output.edit_files(
                [LineObjForTest("a/b.py", line_num=3), LineObjForTest("c/d.py")]
            )
        finally:
            del os.environ["FPP_EDITOR"]
        contents = self.get_output()
        self.assertIn("joe  +3 'a/b.py' 'c/d.py'", contents)
        self.assertIn("exit $?;", contents)

    def test_append_exit_uses_shell_status_variable(self):
        os.environ["SHELL"] = "/usr/bin/fish"
        output.append_exit()
        self.assertIn("exit $status;", self.get_output())


if __name__ == "__main__":
    unittest.main()
