import argparse
import logging
import os
import pathlib
import shutil
import signal
import sys
import tempfile
from typing import Any, Dict, Optional

import yaml

from webviz_ert.assets import WEBVIZ_CONFIG

logger = logging.getLogger()


def run_webviz_ert(experimental_mode: bool = False, verbose: bool = False) -> None:
    signal.signal(signal.SIGINT, handle_exit)
    # The entry point of webviz is to call it from command line, and so do we.

    webviz = shutil.which("webviz")
    if webviz:
        send_ready()
        with tempfile.NamedTemporaryFile() as temp_config:
            project_identifier = os.getenv("ERT_PROJECT_IDENTIFIER", os.getcwd())
            if project_identifier is None:
                logger.error("Unable to find ERT project!")
            create_config(
                project_identifier, WEBVIZ_CONFIG, temp_config, experimental_mode
            )
            os.execl(
                webviz,
                webviz,
                "build",
                temp_config.name,
                "--theme",
                "equinor",
                "--loglevel",
                "DEBUG" if verbose else "WARNING",
            )
    else:
        logger.error("Failed to find webviz")


def send_ready() -> None:
    """
    Tell ERT's BaseService that we're ready, even though we're not actually
    ready to accept requests. At the moment, ERT doesn't interface with
    webviz-ert in any way, so it's not necessary to send the signal later.
    """
    if "ERT_COMM_FD" not in os.environ:
        logger.info("webviz ert is running outside of ert context")
        return
    fd = int(os.environ["ERT_COMM_FD"])
    with os.fdopen(fd, "w") as f:
        f.write("{}")  # Empty, but valid JSON


def handle_exit(
    *_: Any,
) -> None:
    # pylint: disable=logging-not-lazy
    logger.info("\n" + "=" * 32)
    logger.info("Session terminated by the user.\nThank you for using webviz-ert!")
    logger.info("=" * 32)
    sys.tracebacklimit = 0
    sys.stdout = open(os.devnull, "w")
    sys.exit()


def create_config(
    project_identifier: Optional[str],
    config_file: pathlib.Path,
    temp_config: Any,
    experimental_mode: bool,
) -> None:
    with open(config_file, "r") as f:
        config_dict = yaml.safe_load(f)
        for page in config_dict["pages"]:
            for element in page["content"]:
                for key in element:
                    if element[key] is None:
                        element[key] = {"project_identifier": project_identifier}
                    else:
                        element[key]["project_identifier"] = project_identifier

    new_config_dict = config_dict

    def filter_experimental_pages(
        page: Dict[str, Any], experimental_mode: bool
    ) -> bool:
        if "experimental" in page:
            if page["experimental"]:
                return experimental_mode
        return True

    new_config_dict["pages"] = [
        page
        for page in new_config_dict["pages"]
        if filter_experimental_pages(page, experimental_mode)
    ]

    output_str = yaml.dump(new_config_dict)
    temp_config.write(str.encode(output_str))
    temp_config.seek(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--experimental-mode", action="store_true")
    parser.add_argument(
        "--verbose", action="store_true", help="Show verbose output.", default=False
    )
    args = parser.parse_args()

    run_webviz_ert(args.experimental_mode, args.verbose)
