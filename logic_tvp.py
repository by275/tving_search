import json
import re
from copy import deepcopy
from datetime import date, datetime, timedelta

# third-party
from flask import jsonify, render_template

# pylint: disable=import-error
from plugin import PluginModuleBase

# pylint: disable=relative-beyond-top-level
from .logic_common import API, pathscrub
from .setup import P

logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting


class LogicTVP(PluginModuleBase):
    db_default = {
        "tvp_excl_filter_enabled": "True",
        "tvp_excl_filter_episode": "",
        "tvp_excl_filter_program": "",
        "tvp_excl_filter_channels": "",
        "tvp_excl_filter_category": "",
        "tvp_incl_filter": json.dumps(
            {
                "date": "anytime",
                "order": "broadDate",
                "channels": "",
                "category": "",
                "lastonly": "True",
                "quickonly": "False",
            }
        ),
        "tvp_collection_list": json.dumps(
            [
                {"key": "새로 시작한 프로그램", "val": "/highlights?key=AND_RE_VODHOME_NEW_PM_LIST"},
                {"key": "티빙 4K", "val": "/highlights?key=SMTV_PROG_4K"},
                {"key": "티빙 오리지널", "val": "/originals?order=new"},
                {"key": "파라마운트+ 오리지널&독점", "val": "/highlights?key=AND_PARAMOUNT_ORG_PROGRAM_LIST"},
            ]
        ),
    }

    optlist = {
        "date": [
            {"key": "전체기간", "val": "anytime", "sel": ""},
            {"key": "오늘", "val": "today", "sel": ""},
            {"key": "어제", "val": "yesterday", "sel": ""},
            {"key": "이번주", "val": "thisweek", "sel": ""},
            {"key": "이번달", "val": "thismonth", "sel": ""},
        ],
        "order": [
            {"key": "최신순", "val": "broadDate", "sel": ""},
            {"key": "인기순", "val": "viewDay", "sel": ""},
        ],
        "channels": [],
        "category": [],
    }

    PTN_PCODE = re.compile(r"^(P[0-9]+)$")

    def __init__(self, PM):
        super().__init__(PM, None)
        self.name = "tvp"
        self.first_menu = "episodes"

    def plugin_load(self):
        self.optlist["channels"] = [{"key": x["name"], "val": x["code"], "sel": ""} for x in self.tving_channels()]
        self.optlist["category"] = [{"key": x["name"], "val": x["code"], "sel": ""} for x in self.tving_category()]

    def process_menu(self, sub, req):
        arg = ModelSetting.to_dict()
        arg["package_name"] = package_name
        arg["module_name"] = self.name
        arg["tving_installed"] = True
        # pylint: disable=unused-import
        try:
            import tving
        except ImportError:
            arg["tving_installed"] = False

        try:
            if sub == "episodes":
                arg["optlist"] = deepcopy(self.optlist)
                filter_val = json.loads(arg["tvp_incl_filter"])
                default_val = json.loads(self.db_default["tvp_incl_filter"])
                for k, v in arg["optlist"].items():
                    for x in v:
                        if x["val"] in filter_val.get(k, default_val[k]):
                            x.update({"sel": "selected"})
                arg["optlist"]["lastonly"] = filter_val.get("lastonly", default_val["lastonly"]) == "True"
                arg["optlist"]["quickonly"] = filter_val.get("quickonly", default_val["quickonly"]) == "True"
            elif sub == "collections":
                arg["collections"] = json.loads(arg["tvp_collection_list"])
            if sub == "setting":
                return render_template(f"{package_name}_{self.name}_{sub}.html", arg=arg)
            return render_template(f"{package_name}_{self.name}.html", arg=arg, sub=sub)
        except Exception:
            logger.exception("Exception:")
            return render_template("sample.html", title=f"{package_name} - {self.name} - {sub}")

    def process_ajax(self, sub, req):
        try:
            p = req.form.to_dict() if req.method == "POST" else req.args.to_dict()
            page = p.get("page", "1")
            if sub == "episodes":
                uparams = {
                    "order": p.get("order", "broadDate"),
                    "channelCode": p.get("channels", ""),
                    "categoryCode": p.get("category", ""),
                    "multiCategoryCode": p.get("category", ""),
                    "lastFrequency": "Y" if p.get("lastonly", "") == "True" else "N",
                    "quickupYn": "Y" if p.get("quickonly", "") == "True" else "N",
                }
                pdate = p.get("date", "anytime")
                if pdate != "anytime":
                    today = date.today()
                    if pdate == "today":
                        uparams.update(
                            {"broadStartDate": today.strftime("%Y%m%d"), "broadEndDate": today.strftime("%Y%m%d")}
                        )
                    elif pdate == "yesterday":
                        yesterday = (today - timedelta(days=1)).strftime("%Y%m%d")
                        uparams.update({"broadStartDate": yesterday, "broadEndDate": yesterday})
                    elif pdate == "thisweek":
                        weekday = today.isoweekday()
                        sdate = (today - timedelta(days=weekday)).strftime("%Y%m%d")  # SUN
                        uparams.update({"broadStartDate": sdate, "broadEndDate": today.strftime("%Y%m%d")})
                    elif pdate == "thismonth":
                        uparams.update(
                            {"broadStartDate": f'{today.strftime("%Y%m")}01', "broadEndDate": today.strftime("%Y%m%d")}
                        )
                    else:
                        raise NotImplementedError(f"Unknown parameter: date={pdate}")

                excl_filter_enabled = ModelSetting.get_bool("tvp_excl_filter_enabled")
                if excl_filter_enabled:
                    uparams.update(
                        {
                            "notEpisodeCode": ModelSetting.get("tvp_excl_filter_episode").replace(" ", ""),
                            "notProgramCode": ModelSetting.get("tvp_excl_filter_program").replace(" ", ""),
                        }
                    )
                data = self.tving_episodes(uparams=uparams, page=page, excl_filter_enabled=excl_filter_enabled)
                return jsonify({"success": True, "data": data})
            if sub == "search":
                kwd = p.get("keyword", "")
                if not kwd:
                    return jsonify({"success": True, "data": {"list": [], "nomore": True}})
                m = self.PTN_PCODE.search(kwd)
                if m:
                    uparams = {"programCode": kwd, "lastFrequency": "frequencyDesc"}
                    return jsonify({"success": True, "data": self.tving_episodes(uparams=uparams, page=page)})
                return jsonify({"success": True, "data": self.__search(kwd, page=page)})
            if sub == "originals":
                order = p.get("order", "new")
                return jsonify({"success": True, "data": self.__originals(order, page=page)})
            if sub == "highlights":
                uparams = {"positionKey": p.get("key", "")}
                return jsonify({"success": True, "data": self.tving_highlights(uparams=uparams, page=page)})
            if sub == "theme":
                return jsonify({"success": True, "data": self.tving_theme(p.get("sec", ""), page=page)})
            if sub == "save_filter":
                keys = json.loads(self.db_default["tvp_incl_filter"]).keys()
                new_val = {key: p.get(key) for key in keys if key in p}
                ModelSetting.set("tvp_incl_filter", json.dumps(new_val))
                return jsonify({"success": True})
            if sub == "append_filter":
                db_key = p.get("key")
                db_val = ModelSetting.get(db_key)
                if db_val:
                    db_val += ","
                db_val += p.get("val", "")
                ModelSetting.set(db_key, db_val)
                return jsonify({"success": True})
            if sub == "new_collection":
                new_key = p.get("key", "").strip()
                if not new_key:
                    return jsonify(({"success": False, "log": "잘못된 이름"}))
                new_val = p.get("val").strip()
                existing_list = json.loads(ModelSetting.get("tvp_collection_list"))
                if any(True for x in existing_list if x["key"] == new_key):
                    return jsonify(({"success": False, "log": "이미 있는 이름"}))
                ModelSetting.set("tvp_collection_list", json.dumps([{"key": new_key, "val": new_val}] + existing_list))
                return jsonify({"success": True})
            if sub == "save_collection":
                ModelSetting.set("tvp_collection_list", p.get("list"))
                return jsonify({"success": True})
            raise NotImplementedError(f"잘못된 URL: {sub}")
        except Exception as e:
            logger.exception("Exception:")
            return jsonify({"success": False, "log": str(e)})

    def tving_ep_parser_one(self, item):
        epfrq = item["episode"]["frequency"]
        epstr = f"E{epfrq:02d}"
        datestr = str(item["episode"]["broadcast_date"])[2:]

        # air info
        air_info = []
        air_info += [item["channel"]["name"]["ko"]]
        air_info += [item["program"]["category1_name"]["ko"]]
        air_datetime = []
        broad_week = item["program"].get("broad_week", "")
        if broad_week:
            if len(broad_week) == 7:
                air_datetime += ["매일"]
            elif len(broad_week) == 5:
                air_datetime += ["월~금"]
            else:
                air_datetime += [broad_week]
        broad_hour = item["program"].get("broad_hour", "")
        broad_minu = item["program"].get("broad_minu", "")
        if broad_hour and broad_minu:
            air_datetime += [f"{broad_hour}:{broad_minu}"]
        if air_datetime:
            air_info += [" ".join(air_datetime)]
        broad_dt = item["program"].get("broad_dt", "")
        if broad_dt:
            broad_dt = datetime.strptime(broad_dt, "%Y%m%d").strftime("%Y.%m.%d")
        broad_end_dt = item["program"].get("broad_end_dt", "")
        if broad_end_dt:
            broad_end_dt = datetime.strptime(broad_end_dt, "%Y%m%d").strftime("%Y.%m.%d")
        if broad_dt:
            air_info += ["~".join([broad_dt, broad_end_dt])]

        # filaname
        program_name = item["program"]["name"]["ko"]
        program_name = (
            program_name.replace("~", "")
            .replace(",", "")
            .replace("!", "")
            .replace("_", " ")
            .replace("(", "")
            .replace(")", "")
        )
        filename = [pathscrub(program_name.strip(), os="windows", filename=True)]
        if epfrq != 0:
            filename.append(epstr)
        filename.append(datestr)

        # delete irrelevant keys in item
        for k in [
            "asp_info",
            "billing_package_id",
            "billing_package_id_type",
            "program_sale_count",
            "program_view_count",
            "sale_count",
            "view_count",
            "support_info",
        ]:
            try:
                del item[k]
            except Exception:
                pass

        # add processed
        item["p"] = {
            "filename": ".".join(filename),
            "air_info": " | ".join(air_info),
            "datetime": datetime.strptime(str(item["service_open_date"]), "%Y%m%d%H%M%S").isoformat(),
        }

        return item

    def tving_ep_parser(self, items, excl_filter_enabled=False):
        if excl_filter_enabled:
            excl_ch = ModelSetting.get("tvp_excl_filter_channels").replace(" ", "").lower().split(",")
            excl_genre = ModelSetting.get("tvp_excl_filter_category").replace(" ", "").lower().split(",")

        # from items-retrieved-from-api to items-parsed-for-web
        ret = []
        for item in items:
            try:
                if excl_filter_enabled and item["channel"]["name"]["ko"].replace(" ", "").lower() in excl_ch:
                    continue
                if (
                    excl_filter_enabled
                    and item["program"]["category1_name"]["ko"].replace(" ", "").lower() in excl_genre
                ):
                    continue
                parsed_item = self.tving_ep_parser_one(item)
                if bool(parsed_item):
                    ret.append(parsed_item)
            except Exception:
                logger.exception("Exception:")
        return ret

    def __search(self, keyword, page="1"):
        data = API.search(keyword, self.name, page=page)
        codes = [x["mast_cd"] for x in data["list"]]

        ep_list, no_more = [], data["nomore"]
        if codes:
            uparams = {"programCode": ",".join(codes), "lastFrequency": "Y", "notEpisodeCode": "", "notProgramCode": ""}
            ret = self.tving_episodes(uparams=uparams, page="1")

            # NOTE: pageSize for tving_episodes should be larger then or equal to len(codes)
            assert len(codes) == len(
                ret["list"]
            ), f"Incomplete Search: requested {len(codes)} but received {len(ret['list'])}"

            # reorder to match with a searched result
            for code in codes:
                ep_list += [x for x in ret["list"] if x["program"]["code"] == code]
        return {"list": ep_list, "nomore": no_more}

    def __originals(self, order, page="1"):
        data = API.originals(self.name, order, page=page)
        codes = [x["vod_code"] for x in data["list"]]

        ep_list, no_more = [], data["nomore"]
        if codes:
            uparams = {"programCode": ",".join(codes), "lastFrequency": "Y", "notEpisodeCode": "", "notProgramCode": ""}
            ret = self.tving_episodes(uparams=uparams, page="1")
            # reorder to match with a searched result
            for code in codes:
                ep_list += [x for x in ret["list"] if x["program"]["code"] == code]
        return {"list": ep_list, "nomore": no_more}

    def tving_episodes(self, uparams=None, page="1", excl_filter_enabled=False):
        url = "/v2/media/episodes"
        params = {
            "pageNo": page,
            "pageSize": "24",
            "order": "broadDate",
            # "order": "viewDay",
            # "order": "frequencyDesc",
            "adult": "all",
            "free": "all",
            "guest": "all",
            "scope": "all",
            "quickupYn": "N",
            "lastFrequency": "Y",
            "episodeCode": "",
            "notEpisodeCode": "",
            "programCode": "",
            "notProgramCode": "",
            "personal": "N",
        }
        # not을 포함한 제외필터가 우선함
        params.update(uparams or {})
        data = API.get(url, params=params)

        ep_list = data["body"]["result"]
        no_more = data["body"]["has_more"].lower() != "y"
        return {
            "list": self.tving_ep_parser(ep_list, excl_filter_enabled=excl_filter_enabled) if ep_list else [],
            "nomore": no_more,
        }

    def tving_highlights(self, uparams=None, page="1"):
        ep_list, no_more = API.highlights(uparams=uparams, page=page)
        return {"list": self.tving_ep_parser(ep_list) if ep_list else [], "nomore": no_more}

    def tving_theme(self, seq, uparams=None, page="1"):
        if len(seq.split("/")) != 2:
            params = {"pocCode": "POCD0400", "pageNo": "1", "pageSize": "10", "themeType": "T", "status": "Y"}
            data = API.get(f"/v2/operator/theme/{seq}", params=params)
            section_seq = data["body"]["result"]["sections"][0]["section_seq"]
            seq = f"{seq}/{section_seq}"

        url = f"/v2/operator/theme/{seq}"
        params = {
            "pocCode": "POCD0400",
            "pageNo": page,
            "pageSize": "150",
            "themeType": "T",
        }
        params.update(uparams or {})
        data = API.get(url, params=params)

        ep_list = [x["content"] for x in data["body"]["result"]]
        no_more = data["body"]["has_more"].lower() != "y"
        return {"list": self.tving_ep_parser(ep_list) if ep_list else [], "nomore": no_more}

    def tving_channels(self):
        url = "/v2/operator/highlights"
        params = {
            "positionKey": "AND_VOD_CHNLLIST",
            "cacheTime": "5",
        }
        data = API.get(url, params=params)
        return [{"code": x["content_code"], "name": x["mapping_contents_name"]} for x in data["body"]["result"]]

    def tving_category(self):
        """대분류
        /v2/media/programcatsdtl에서 상세카테고리(소분류)를 얻을 수 있다.
        """
        url = "/v2/media/programcats"
        params = {
            "pageNo": "1",
            "pageSize": "10",
            "order": "name",
        }
        data = API.get(url, params=params)
        return [{"code": x["cate_cd"], "name": x["cate_nm"]} for x in data["body"]["result"]]
