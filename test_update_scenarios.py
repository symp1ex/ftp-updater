import os
import subprocess
import unittest
from types import SimpleNamespace
from unittest import mock

import update_scenarios


RESET_ENVIRONMENT_VARIABLE = "PYINSTALLER_RESET_ENVIRONMENT"


class RunExitCommandTests(unittest.TestCase):
    def test_post_update_process_receives_reset_environment(self):
        parent_env = os.environ.copy()
        parent_env.pop(RESET_ENVIRONMENT_VARIABLE, None)
        parent_env["TEST_UPDATER_ENV"] = "value"

        with mock.patch.dict(os.environ, parent_env, clear=True):
            with mock.patch.object(update_scenarios.subprocess, "Popen") as popen:
                result = update_scenarios.run_exit_command(
                    SimpleNamespace(),
                    "application.exe",
                    r"C:\application",
                )

        self.assertTrue(result)
        child_env = popen.call_args.kwargs["env"]
        self.assertEqual(child_env["TEST_UPDATER_ENV"], "value")
        self.assertEqual(child_env[RESET_ENVIRONMENT_VARIABLE], "1")

    def test_parent_environment_is_not_mutated(self):
        parent_env = os.environ.copy()
        parent_env.pop(RESET_ENVIRONMENT_VARIABLE, None)

        with mock.patch.dict(os.environ, parent_env, clear=True):
            original_env = os.environ.copy()
            with mock.patch.object(update_scenarios.subprocess, "Popen"):
                update_scenarios.run_exit_command(
                    SimpleNamespace(),
                    "application.exe",
                    r"C:\application",
                )

            self.assertEqual(os.environ.copy(), original_env)
            self.assertNotIn(RESET_ENVIRONMENT_VARIABLE, os.environ)

    def test_existing_popen_parameters_are_preserved(self):
        command = '"application.exe" --argument "value"'
        application_directory = r"C:\application"

        with mock.patch.object(update_scenarios.subprocess, "Popen") as popen:
            result = update_scenarios.run_exit_command(
                SimpleNamespace(),
                command,
                application_directory,
            )

        self.assertTrue(result)
        args, kwargs = popen.call_args
        self.assertEqual(args, (["cmd.exe", "/d", "/c", command],))
        self.assertEqual(
            set(kwargs),
            {"cwd", "creationflags", "env"},
        )
        self.assertEqual(kwargs["cwd"], application_directory)
        self.assertEqual(
            kwargs["creationflags"],
            getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        expected_env = os.environ.copy()
        expected_env[RESET_ENVIRONMENT_VARIABLE] = "1"
        self.assertEqual(kwargs["env"], expected_env)

    def test_existing_reset_environment_value_is_overridden_only_for_child(self):
        with mock.patch.dict(
                os.environ,
                {RESET_ENVIRONMENT_VARIABLE: "0"},
                clear=False):
            original_env = os.environ.copy()
            with mock.patch.object(update_scenarios.subprocess, "Popen") as popen:
                update_scenarios.run_exit_command(
                    SimpleNamespace(),
                    "application.exe",
                    r"C:\application",
                )

            child_env = popen.call_args.kwargs["env"]
            self.assertEqual(child_env[RESET_ENVIRONMENT_VARIABLE], "1")
            self.assertEqual(
                os.environ[RESET_ENVIRONMENT_VARIABLE],
                "0",
            )
            self.assertEqual(os.environ.copy(), original_env)


if __name__ == "__main__":
    unittest.main()
