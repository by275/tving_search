__menu = {
    "uri": __package__,
    "name": "티빙 검색",
    "list": [
        {
            "uri": "tvp",
            "name": "TV 프로그램",
            "list": [
                {"uri": "setting", "name": "설정"},
                {"uri": "episodes", "name": "에피소드"},
                {"uri": "collections", "name": "콜렉션"},
                {"uri": "search", "name": "검색"},
            ],
        },
        {
            "uri": "mov",
            "name": "영화",
            "list": [
                {"uri": "setting", "name": "설정"},
                {"uri": "movies", "name": "영화"},
                {"uri": "collections", "name": "콜렉션"},
                {"uri": "search", "name": "검색"},
            ],
        },
        {
            "uri": "etc",
            "name": "기타",
            "list": [
                {"uri": "ratings", "name": "시청률"},
            ],
        },
        {
            "uri": "log",
            "name": "로그",
        },
    ],
}

setting = {
    "filepath": __file__,
    "use_db": True,
    "use_default_setting": True,
    "home_module": "tvp",
    "menu": __menu,
    "setting_menu": None,
    "default_route": "normal",
}

# pylint: disable=import-error
from plugin import create_plugin_instance

P = create_plugin_instance(setting)

from .logic_etc import LogicETC
from .logic_mov import LogicMOV
from .logic_tvp import LogicTVP

P.set_module_list([LogicTVP, LogicMOV, LogicETC])
