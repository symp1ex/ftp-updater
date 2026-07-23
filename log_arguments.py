import argparse
import sys


DEFAULT_LOGS_DIR = "logs"
DEFAULT_LOGS_LEVEL = "INFO"
DEFAULT_LOGS_CLEAR_DAYS = 2

VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class NonExitingArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def normalize_log_level(value, default=DEFAULT_LOGS_LEVEL):
    if not isinstance(value, str):
        return default

    level = value.upper()
    if level in VALID_LOG_LEVELS:
        return level
    return default


def parse_logs_level_cli(value):
    level = normalize_log_level(value, default=None)
    if level is None:
        raise argparse.ArgumentTypeError(
            "expected one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"
        )
    return level


def parse_logs_clear_cli(value):
    try:
        days = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("expected a non-negative integer")

    if days < 0:
        raise argparse.ArgumentTypeError("expected a non-negative integer")
    return days


def parse_early_logging_arguments(argv=None):
    argv = sys.argv[1:] if argv is None else argv

    parser = NonExitingArgumentParser(add_help=False)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--upgrade", action="store_true")
    parser.add_argument("--logs-dir", dest="logs_dir")
    parser.add_argument("--logs-level", dest="logs_level")
    parser.add_argument("--logs-clear", dest="logs_clear")

    try:
        args, _ = parser.parse_known_args(argv)
    except Exception:
        return argparse.Namespace(
            check=False,
            upgrade=False,
            logs_dir=None,
            logs_level=None,
            logs_clear=None,
        )

    if not (args.check or args.upgrade):
        args.logs_dir = None
        args.logs_level = None
        args.logs_clear = None

    return args


def has_logging_overrides(args):
    return (
        args.logs_dir is not None
        or args.logs_level is not None
        or args.logs_clear is not None
    )
