# -*- coding: utf-8 -*-
from .plugin import plugin as p

blueprint = p.blueprint
menu = p.menu
plugin_info = p.plugin_info

plugin_load = p.logic.plugin_load
plugin_unload = p.logic.plugin_unload

# for other plugins
Logic = p.module_list[0]
