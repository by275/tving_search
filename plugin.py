# -*- coding: utf-8 -*-
#########################################################
# 고정영역
#########################################################
# python
import os
import re
import json
import traceback

# third-party
from flask import Blueprint, request, render_template, redirect, jsonify, Response
from flask_login import login_required

# sjva 공용
from framework.logger import get_logger
from framework import app, db, scheduler, check_api

# 패키지
package_name = __name__.split('.')[0]
logger = get_logger(package_name)

from .logic import Logic
from .model import ModelSetting

blueprint = Blueprint(
    package_name, package_name,
    url_prefix='/%s' % package_name,
    template_folder=os.path.join(os.path.dirname(__file__), 'templates')
)


def plugin_load():
    Logic.plugin_load()


def plugin_unload():
    Logic.plugin_unload()


plugin_info = {
    "category_name": "vod",
    "version": "0.0.2",
    "name": "tving_info",
    "home": "https://github.com/wiserain/tving_info",
    "more": "https://github.com/wiserain/tving_info",
    "description": "티빙 실시간 정보를 보여주는 SJVA 플러그인",
    "developer": "wiserain",
    "zip": "https://github.com/wiserain/tving_info/archive/main.zip",
    "icon": "",
}
#########################################################


# 메뉴 구성.
menu = {
    'main': [package_name, '티빙 정보'],
    'sub': [
        ['setting', '설정'], ['episode', '에피소드'], ['log', '로그']
    ],
    'category': 'vod',
}


#########################################################
# WEB Menu
#########################################################
@blueprint.route('/')
def home():
    return redirect('/%s/episode' % package_name)


@blueprint.route('/<sub>')
@login_required
def detail(sub):
    if sub == 'setting':
        arg = ModelSetting.to_dict()
        arg['package_name'] = package_name
        return render_template('%s_setting.html' % package_name, sub=sub, arg=arg)
    elif sub == 'episode':
        arg = ModelSetting.to_dict()
        arg['package_name'] = package_name
        return render_template('%s_episode.html' % package_name, arg=arg)
    elif sub == 'log':
        return render_template('log.html', package=package_name)
    return render_template('sample.html', title='%s - %s' % (package_name, sub))


#########################################################
# For UI                                                          
#########################################################
@blueprint.route('/ajax/<sub>', methods=['GET', 'POST'])
@login_required
def ajax(sub):
    try:
        p = request.form.to_dict() if request.method == 'POST' else request.args.to_dict()
        # 설정 저장
        if sub == 'setting_save':
            ret = Logic.setting_save(request)
            return jsonify(ret)
        elif sub == 'episode':
            search = p.get('search', '')
            page = p.get('page', '1')

            new_params = {}
            if search:
                m = re.compile('^(P[0-9]+)$').search(search)
                pcodes = [search] if m else Logic.tving_search(search)
                if pcodes:
                    new_params.update({'programCode': ','.join(pcodes), "lastFrequency": 'Y'})
                    if len(pcodes) == 1:
                        new_params.update({'order': 'frequencyDesc', 'lastFrequency': 'N'})
            ret = Logic.tving_episodes(new_params=new_params, page=page)
            return jsonify({'success': True, 'episodes': ret})
        elif sub == 'append_filter':
            db_key = p.get('key')
            db_val = ModelSetting.get(db_key)
            if db_val:
                db_val += ','
            db_val += p.get('val', '')
            ModelSetting.set(db_key, db_val)
            return jsonify({'success': True})
    except Exception as e:
        logger.error('Exception: %s', str(e))
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'log': str(e)})
