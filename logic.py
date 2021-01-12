# -*- coding: utf-8 -*-
#########################################################
# python
import os
import re
import sys
import traceback
from datetime import datetime
import platform
import ntpath

try:
    from urllib import quote  # Python 2.X
except ImportError:
    from urllib.parse import quote  # Python 3+

# third-party
import requests

# sjva 공용
from framework import db, scheduler, app
from framework.util import Util

# 패키지
from .plugin import logger, package_name
from .model import ModelSetting, db_file

ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) ' \
     'Chrome/69.0.3497.100 Safari/537.36'

#########################################################

os_mode = None  # Can be 'windows', 'mac', 'linux' or None. None will auto-detect os.
# Replacement order is important, don't use dicts to store
platform_replaces = {
    'windows': [
        ['[:*?"<>| ]+', ' '],  # Turn illegal characters into a space
        [r'[\.\s]+([/\\]|$)', r'\1'],
    ],  # Dots cannot end file or directory names
    'mac': [['[: ]+', ' ']],  # Only colon is illegal here
    'linux': [],  # No illegal chars
}

def pathscrub(dirty_path, os=None, filename=False):
    """
    Strips illegal characters for a given os from a path.
    :param dirty_path: Path to be scrubbed.
    :param os: Defines which os mode should be used, can be 'windows', 'mac', 'linux', or None to auto-detect
    :param filename: If this is True, path separators will be replaced with '-'
    :return: A valid path.
    """

    # See if global os_mode has been defined by pathscrub plugin
    if os_mode and not os:
        os = os_mode

    if not os:
        # If os is not defined, try to detect appropriate
        drive, path = ntpath.splitdrive(dirty_path)
        if sys.platform.startswith('win') or drive:
            os = 'windows'
        elif sys.platform.startswith('darwin'):
            os = 'mac'
        else:
            os = 'linux'
    replaces = platform_replaces[os]

    # Make sure not to mess with windows drive specifications
    drive, path = ntpath.splitdrive(dirty_path)

    if filename:
        path = path.replace('/', ' ').replace('\\', ' ')
    # Remove spaces surrounding path components
    path = '/'.join(comp.strip() for comp in path.split('/'))
    if os == 'windows':
        path = '\\'.join(comp.strip() for comp in path.split('\\'))
    for search, replace in replaces:
        path = re.sub(search, replace, path)
    path = path.strip()
    # If we stripped everything from a filename, complain
    if filename and dirty_path and not path:
        raise ValueError(
            'Nothing was left after stripping invalid characters from path `%s`!' % dirty_path
        )
    return drive + path


class Logic(object):
    # 디폴트 세팅값
    db_default = {
        'page_size': '24',
        'release_suffix': 'TVING',
        'vcode_exclude': '',
        'channel_exclude': '',
        'channel_include': '',
        'last_only': 'False',
        'searched_key': '',
        'searched_val': '',
        'searched_at': '',
    }

    @staticmethod
    def db_init():
        try:
            for key, value in Logic.db_default.items():
                if db.session.query(ModelSetting).filter_by(key=key).count() == 0:
                    db.session.add(ModelSetting(key, value))
            db.session.commit()
        except Exception as e:
            logger.error('Exception: %s', str(e))
            logger.error(traceback.format_exc())

    @staticmethod
    def plugin_load():
        try:
            # DB 초기화
            Logic.db_init()

            # 편의를 위해 json 파일 생성
            from .plugin import plugin_info
            Util.save_from_dict_to_json(plugin_info, os.path.join(os.path.dirname(__file__), 'info.json'))

            #
            # 자동시작 옵션이 있으면 보통 여기서
            #
        except Exception as e:
            logger.error('Exception: %s', str(e))
            logger.error(traceback.format_exc())

    @staticmethod
    def plugin_unload():
        try:
            logger.debug('%s plugin_unload', package_name)
        except Exception as e:
            logger.error('Exception: %s', str(e))
            logger.error(traceback.format_exc())

    @staticmethod
    def setting_save(req):
        try:
            for key, value in req.form.items():
                logger.debug('Key:%s Value:%s', key, value)
                entity = db.session.query(ModelSetting).filter_by(key=key).with_for_update().first()
                entity.value = value
            db.session.commit()
            return True
        except Exception as e:
            logger.error('Exception: %s', str(e))
            logger.error(traceback.format_exc())
            return False

    # 기본 구조 End
    ##################################################################

    @staticmethod
    def tving_parser(item):
        # 포스터
        poster = [x['url'] for x in item['program']['image'] if x['code'] == 'CAIP0900']

        epfrq = item['episode']['frequency']
        epstr = 'E{:02d}'.format(epfrq)
        datestr = str(item['episode']['broadcast_date'])[2:]

        # 방영 정보
        air_info = []
        air_info += [item['channel']['name']['ko']]
        air_info += [item['program']['category1_name']['ko']]
        air_datetime = []
        broad_week = item['program']['broad_week']
        if broad_week:
            if len(broad_week) == 7:
                air_datetime += ['매일']
            elif len(broad_week) == 5:
                air_datetime += ['월~금']
            else:
                air_datetime += [broad_week]
        if item['program']['broad_hour'] and item['program']['broad_minu']:
            air_datetime += ['{}:{}'.format(item['program']['broad_hour'], item['program']['broad_minu'])]
        if air_datetime:
            air_info += [' '.join(air_datetime)]
        if item['program']['broad_dt']:
            broad_dt = datetime.strptime(item['program']['broad_dt'], '%Y%m%d').strftime('%Y.%m.%d')
        else:
            broad_dt = ''
        if item['program']['broad_end_dt']:
            broad_end_dt = datetime.strptime(item['program']['broad_end_dt'], '%Y%m%d').strftime('%Y.%m.%d')
        else:
            broad_end_dt = ''
        if broad_dt:
            air_info += ['~'.join([broad_dt, broad_end_dt])]

        # 파일이름
        program_name = item['program']['name']['ko']
        program_name = program_name.replace('~', '').replace(',', '').replace('!', '').replace('_', ' ').replace('(', '').replace(')', '')
        filename = [pathscrub(program_name.strip(), os='windows', filename=True)]
        if epfrq != 0:
            filename.append(epstr)
        filename.append(datestr)
        filename.append('1080p')
        release_suffix = ModelSetting.get('release_suffix')
        if release_suffix:
            filename[-1] += '-' + release_suffix
        filename = '.'.join(filename) + '.mp4'

        # 들어오는건 api에서 episodes list를 받을 때는 service_open_date로 정렬되어 들어오지만
        # 서버에 영상이 준비되고 오픈되는 시간은 저마다 다른데 아마도 insert_date와 관련이 있을 듯
        return {
            'id': item['id'],
            'filename': filename,
            'poster_url': 'https://image.tving.com' + poster[0] + '/dims/resize/236' if poster else '',
            'is_qvod': (item['program']['quickup_yn'].upper() == 'Y') and ('quickvod' in item['episode']['pip_media_url']),
            'air_info': ' | '.join(air_info),
            'datetime': datetime.strptime(str(item['service_open_date']), '%Y%m%d%H%M%S').isoformat(),
            'raw': item, 
        }

    @staticmethod
    def tving_search(keyword):
        # from search cache
        if keyword == ModelSetting.get('searched_key'):
            searched_at = datetime.fromisoformat(ModelSetting.get('searched_at'))
            if (datetime.now() - searched_at).total_seconds() <= 60:
                return [x for x in ModelSetting.get('searched_val').split(',')]
        referer = 'https://www.tving.com/find/main.do?kwd=' + quote(keyword.encode('utf8'))
        api_url = "https://search.tving.com/search/getSearch.jsp"
        params = {
            "kwd": keyword,
            "notFoundText": keyword,
            "siteName": "TVING_WEB",
            # "category": "TOTAL",
            'category': 'PROGRAM',
            "pageNum": '1',
            "pageSize": '15',
            "indexType": "both",
            "methodType": "allwordthruindex",
            "payFree": "ALL",
            "runTime": "ALL",
            "grade": "ALL",
            "genre": "ALL",
            "screen": "CSSD0100",
            "os": "CSOD0900",
            "network": "CSND0900",
            "sort1": "score",
            # 'sort1': 'ins_dt',
            "sort2": "NO",
            # 'sort2': 'frequency',
            "sort3": "NO",
            "type1": "desc",
            "type2": "desc",
            "type3": "desc",
            "fixedType": "Y",
            "spcMethod": "someword",
            "spcSize": "0",
            "schReqCnt": "15",
            "vodBCReqCnt": "15",
            "programReqCnt": "18",
            "vodMVReqCnt": "15",
            "smrclipReqCnt": "15",
            "pickClipReqCnt": "15",
            "aloneReqCnt": "15",
            "cSocialClipCnt": "0",
            "boardReqCnt": "0",
            "talkReqCnt": "0",
            "nowTime": "",
            "mode": "normal",
            "adult_yn": "",
            "reKwd": "",
            "xwd": "",
        }
        ret = []
        try:
            res = requests.get(api_url, headers={'referer': referer, 'user-agent': ua}, params=params)
            res.raise_for_status()
            data = res.json()
            if int(data['programRsb']['count']) > 0:
                ret = [x['mast_cd'] for x in data['programRsb']['dataList']]
        except Exception as e:
            logger.error('Exception: %s', str(e))
            logger.error(traceback.format_exc())
        
        # to search cache
        if ret:
            ModelSetting.set('searched_val', ','.join(ret))
        return ret

    @staticmethod
    def tving_episodes(new_params={}, page='1'):
        api_url = 'http://api.tving.com/v2/media/episodes'
        referer = 'http://www.tving.com/vod/home'
        params = {
            "pageNo": page,
            "pageSize": ModelSetting.get('page_size'),
            "order": "broadDate",
            # "order": "frequencyDesc",
            "adult": "all",
            "free": "all",
            "guest": "all",
            "scope": "all",
            "lastFrequency": 'Y' if ModelSetting.get_bool('last_only') else 'N',
            # "programCode": '',
            "notEpisodeCode": ','.join(x.strip() for x in ModelSetting.get('vcode_exclude').split(',')),
            "personal": "N",
            "screenCode": "CSSD0100",
            "networkCode": "CSND0900",
            "osCode": "CSOD0900",
            "teleCode": "CSCD0900",
            "apiKey": "1e7952d0917d6aab1f0293a063697610",
        }

        if bool(new_params):
            params.update(new_params)

        headers = {'referer': referer, 'user-agent': ua}

        tving_ep_list = []
        tving_has_more = False
        try:
            res = requests.get(api_url, headers=headers, params=params).json()
            if res['header']['status'] == 200:
                tving_ep_list = res['body']['result']
                tving_has_more = res['body']['has_more'].lower() == 'y'
        except Exception as e:
            logger.error('Exception: %s', str(e))
            logger.error(traceback.format_exc())

        # 정렬 문제
        # tving_ep_list = sorted(tving_ep_list, key=lambda x: x['insert_date'], reverse=True)

        # 채널 필터
        ch_incl = [x.strip().replace(' ', '').lower() for x in ModelSetting.get('channel_include').split(',') if x.strip()]
        ch_excl = [x.strip().replace(' ', '').lower() for x in ModelSetting.get('channel_exclude').split(',') if x.strip()]
        if ch_excl:
            tving_ep_list = [x for x in tving_ep_list if x['channel']['name']['ko'].strip().replace(' ', '').lower() not in ch_excl]
        elif ch_incl:
            tving_ep_list = [x for x in tving_ep_list if x['channel']['name']['ko'].strip().replace(' ', '').lower() in ch_incl]
        
        # from items retrieved to items parsed
        processed_ep_list = []
        try:
            for item_db in tving_ep_list:
                rss_item_dict = Logic.tving_parser(item_db)
                if bool(rss_item_dict):
                    processed_ep_list.append(rss_item_dict)
        except Exception as e:
            logger.error('Exception: %s', str(e))
            logger.error(traceback.format_exc())

        return {'list': processed_ep_list, 'has_more': tving_has_more}
