# -*- encoding: utf-8 -*-
"""This module provides the capability to create a new hammer version."""
import attr
from pathlib import Path
from logzero import logger
from clix import helpers
from clix.libtools import hammer, subman


@attr.s()
class LibMaker:
    cli_name = attr.ib(default=None)
    cli_version = attr.ib(default=None)
    data_dir = attr.ib(default=None)

    def __attrs_post_init__(self):
        if not self.cli_name:
            clis = helpers.get_cli_list(data_dir=self.data_dir)
            if clis:
                self.cli_name = clis[0]
            else:
                logger.warning("No known CLIs found! Try exploring.")
                return

        if not self.cli_version:
            self.cli_version = helpers.get_latest(self.cli_name, self.data_dir)

        self.MakerClass = None
        if self.cli_name.lower() == "hammer":
            self.MakerClass = hammer.HammerMaker
        elif self.cli_name.lower() == "subscription-manager":
            self.MakerClass = subman.SubManMaker
        else:
            logger.warning(f"I don't know how to make a library for {self.cli_name}")

    def make_lib(self):
        if not self.MakerClass:
            return
        logger.info(
            f"Making a {self.cli_name} library for {self.cli_version}"
            f" at {self.data_dir}libs/generated/{self.cli_name}/"
        )
        cli_dict = helpers.load_cli(self.cli_name, self.cli_version, self.data_dir)
        lib_maker = self.MakerClass(
            cli_dict=cli_dict,
            cli_name=self.cli_name,
            cli_version=self.cli_version,
            data_dir=self.data_dir,
        )
        lib_maker.make()
