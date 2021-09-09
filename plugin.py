# -*- coding: utf-8 -*-
import os

# third-party
from flask import Blueprint

# pylint: disable=import-error
from framework.logger import get_logger
from framework.common.plugin import get_model_setting, Logic, default_route


class PlugIn(object):
    package_name = __name__.split(".")[0]
    logger = get_logger(package_name)
    ModelSetting = get_model_setting(package_name, logger)

    blueprint = Blueprint(
        package_name,
        package_name,
        url_prefix=f"/{package_name}",
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    )

    plugin_info = {
        "category_name": "vod",
        "version": "0.2.0",
        "name": "tving_search",
        "home": "https://github.com/by275/tving_search",
        "more": "https://github.com/by275/tving_search",
        "description": "티빙 검색 플러그인",
        "developer": "by275",
        "zip": "https://github.com/by275/tving_search/archive/main.zip",
        "icon": "",
    }

    menu = {
        "main": [package_name, "티빙 검색"],
        "sub": [["tvp", "TV 프로그램"], ["mov", "영화"], ["log", "로그"]],
        "sub2": {
            "tvp": [
                ["setting", "설정"],
                ["episodes", "에피소드"],
                ["collections", "콜렉션"],
                ["search", "검색"],
            ],
            "mov": [
                ["setting", "설정"],
                ["movies", "영화"],
                ["collections", "콜렉션"],
                ["search", "검색"],
            ],
        },
        "category": "vod",
    }
    home_module = "tvp"

    module_list = None
    logic = None

    def __init__(self):
        from framework import app, path_data

        db_file = os.path.join(path_data, "db", f"{self.package_name}.db")
        app.config["SQLALCHEMY_BINDS"][self.package_name] = f"sqlite:///{db_file}"

        from framework.util import Util

        Util.save_from_dict_to_json(self.plugin_info, os.path.join(os.path.dirname(__file__), "info.json"))


plugin = PlugIn()

# pylint: disable=relative-beyond-top-level
from .logic_tvp import LogicTVP
from .logic_mov import LogicMOV

plugin.module_list = [LogicTVP(plugin), LogicMOV(plugin)]

# (logger, package_name, module_list, ModelSetting) required for Logic
plugin.logic = Logic(plugin)
# (logger, package_name, module_list, ModelSetting, blueprint, logic) required for default_route
default_route(plugin)
