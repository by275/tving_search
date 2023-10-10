import json
import re
from copy import deepcopy
from datetime import datetime

# third-party
from flask import jsonify, render_template

# pylint: disable=import-error
from plugin import PluginModuleBase

# pylint: disable=relative-beyond-top-level
from .logic_common import API
from .setup import P

logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting

grade_code_map = {"CMMG0100": "전체", "CMMG0200": "12세", "CMMG0300": "15세", "CMMG0400": "19세"}


class LogicMOV(PluginModuleBase):
    db_default = {
        "mov_excl_filter_enabled": "True",
        "mov_excl_filter_movie": "",
        "mov_excl_filter_category": "",
        "mov_incl_filter": json.dumps(
            {
                "type": "all",
                "order": "new",
                "category": "",
                "diversityonly": "False",
            }
        ),
        "mov_collection_list": json.dumps(
            [
                {"key": "티빙 4K", "val": "/highlights?key=SMTV_MV_4K"},
                {"key": "티빙 오리지널&독점", "val": "/highlights?key=AND_RE_MOVIEHOME_HOT_MV_LIST"},
                {"key": "티빙 오리지널", "val": "/originals?order=new"},
            ]
        ),
    }

    optlist = {
        "order": [
            {"key": "최신순", "val": "new", "sel": ""},
            {"key": "인기순", "val": "viewDay", "sel": ""},
        ],
        "category": [],
    }

    PTN_MCODE = re.compile(r"^(M[0-9]+)$")

    def __init__(self, PM):
        super().__init__(PM, None)
        self.name = "mov"
        self.first_menu = "movies"

    def plugin_load(self):
        self.optlist["category"] = [{"key": x["name"], "val": x["code"], "sel": ""} for x in self.tving_category()]

    def process_menu(self, sub, req):
        arg = ModelSetting.to_dict()
        arg["package_name"] = package_name
        arg["module_name"] = self.name
        arg["tving_installed"] = True
        # pylint: disable=unused-import,import-outside-toplevel
        try:
            import tving
        except ImportError:
            arg["tving_installed"] = False

        try:
            if sub == "movies":
                arg["optlist"] = deepcopy(self.optlist)
                filter_val = json.loads(arg["mov_incl_filter"])
                default_val = json.loads(self.db_default["mov_incl_filter"])
                for k, v in arg["optlist"].items():
                    for x in v:
                        if x["val"] in filter_val.get(k, default_val[k]):
                            x.update({"sel": "selected"})
                arg["optlist"]["diversityonly"] = (
                    filter_val.get("diversityonly", default_val["diversityonly"]) == "True"
                )
            elif sub == "collections":
                arg["collections"] = json.loads(arg["mov_collection_list"])
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
            if sub == "movies":
                uparams = {
                    "order": p.get("order", "new"),
                    "categoryCode": p.get("category", ""),
                    "diversityYn": "Y" if p.get("diversityonly", "") == "True" else "",
                }

                excl_filter_enabled = ModelSetting.get_bool("mov_excl_filter_enabled")
                if excl_filter_enabled:
                    uparams.update({"notMovieCode": ModelSetting.get("mov_excl_filter_movie").replace(" ", "")})
                data = self.tving_movies(uparams=uparams, page=page, excl_filter_enabled=excl_filter_enabled)
                return jsonify({"success": True, "data": data})
            if sub == "search":
                kwd = p.get("keyword", "")
                if not kwd:
                    return jsonify({"success": True, "data": {"list": [], "nomore": True}})
                m = self.PTN_MCODE.search(kwd)
                if m:
                    uparams = {"movieCode": kwd, "notMovieCode": ""}
                    return jsonify({"success": True, "data": self.tving_movies(uparams=uparams, page=page)})
                return jsonify({"success": True, "data": self.__search(kwd, page=page)})
            if sub == "originals":
                order = p.get("order", "new")
                return jsonify({"success": True, "data": self.__originals(order, page=page)})
            if sub == "highlights":
                uparams = {"positionKey": p.get("key", "")}
                return jsonify({"success": True, "data": self.tving_highlights(uparams=uparams, page=page)})
            if sub == "curation":
                return jsonify({"success": True, "data": self.tving_curation(p.get("code", ""))})
            if sub == "save_filter":
                keys = json.loads(self.db_default["mov_incl_filter"]).keys()
                new_val = {key: p.get(key) for key in keys if key in p}
                ModelSetting.set("mov_incl_filter", json.dumps(new_val))
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
                existing_list = json.loads(ModelSetting.get("mov_collection_list"))
                if any(True for x in existing_list if x["key"] == new_key):
                    return jsonify(({"success": False, "log": "이미 있는 이름"}))
                ModelSetting.set("mov_collection_list", json.dumps([{"key": new_key, "val": new_val}] + existing_list))
                return jsonify({"success": True})
            if sub == "save_collection":
                ModelSetting.set("mov_collection_list", p.get("list"))
                return jsonify({"success": True})
            raise NotImplementedError(f"잘못된 URL: {sub}")
        except Exception as e:
            logger.exception("Exception:")
            return jsonify({"success": False, "log": str(e)})

    def tving_mv_parser_one(self, item):
        try:
            grade_txt = [grade_code_map[item["movie"]["grade_code"]]]
        except Exception:
            grade_txt = [item["movie"]["grade_code"]]
        release_date = str(item["movie"].get("release_date", "0"))
        try:
            service_open_date = datetime.strptime(str(item["service_open_date"]), "%Y%m%d%H%M%S").isoformat()
        except Exception:
            # not available for objects from curation api
            service_open_date = ""

        # 릴리즈 정보
        summary = []
        summary += [item["movie"]["category1_name"]["ko"]]

        duration = divmod(int(item["movie"]["duration"]), 60)[0]
        if duration > 0:
            summary += [f"{str(duration)}분"]
        if len(release_date) == 8:
            summary += [f"{release_date} 공개"]

        # 캐스팅 정보
        casting = item["movie"].get("actor", [])
        if len(casting) > 4:
            casting = casting[:5]
            casting[-1] += " 외"

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
            "summary": " | ".join(summary),
            "director": ", ".join(item["movie"].get("director", [])),
            "casting": ", ".join(casting),
            "grade": grade_txt,
            "datetime": service_open_date,
        }

        return item

    def tving_mv_parser(self, items, excl_filter_enabled=False):
        if excl_filter_enabled:
            excl_genre = ModelSetting.get("mov_excl_filter_category").replace(" ", "").lower().split(",")

        # from items-retrieved-from-api to items-parsed-for-web
        ret = []
        for item in items:
            try:
                parsed_item = self.tving_mv_parser_one(item)
                if (
                    excl_filter_enabled
                    and parsed_item["movie"]["category1_name"]["ko"].replace(" ", "").lower() in excl_genre
                ):
                    continue
                if bool(parsed_item):
                    ret.append(parsed_item)
            except Exception:
                logger.exception("Exception:")
        return ret

    def __search(self, keyword, page="1"):
        data = API.search(keyword, self.name, page=page)
        codes = [x["mast_cd"] for x in data["list"]]

        mv_list, no_more = [], data["nomore"]
        if codes:
            uparams = {"movieCode": ",".join(codes), "notMovieCode": ""}
            ret = self.tving_movies(uparams=uparams, page="1")

            # NOTE: pageSize for tving_movies should be larger then or equal to len(codes)
            assert len(codes) == len(
                ret["list"]
            ), f"Incomplete Search: requested {len(codes)} but received {len(ret['list'])}"

            # reorder to match with a searched result
            for code in codes:
                mv_list += [x for x in ret["list"] if x["movie"]["code"] == code]
        return {"list": mv_list, "nomore": no_more}

    def __originals(self, order, page="1"):
        data = API.originals(self.name, order, page=page)
        codes = [x["vod_code"] for x in data["list"]]

        mv_list, no_more = [], data["nomore"]
        if codes:
            uparams = {"movieCode": ",".join(codes), "notMovieCode": ""}
            ret = self.tving_movies(uparams=uparams, page="1")
            # reorder to match with a searched result
            for code in codes:
                mv_list += [x for x in ret["list"] if x["movie"]["code"] == code]
        return {"list": mv_list, "nomore": no_more}

    def tving_movies(self, uparams=None, page="1", excl_filter_enabled=False):
        url = "/v2/media/movies"
        params = {
            "pageNo": page,
            "pageSize": "24",
            "order": "new",
            "adult": "all",
            "free": "all",
            "guest": "all",
            "scope": "all",
            "movieCode": "",
            "notMovieCode": "",
            "categoryCode": "",
            "productPackageCode": "2610061,2610161,261062",
            "personal": "N",
        }
        params.update(uparams or {})
        data = API.get(url, params=params)

        mv_list = data["body"]["result"]
        no_more = data["body"]["has_more"].lower() != "y"
        return {
            "list": self.tving_mv_parser(mv_list, excl_filter_enabled=excl_filter_enabled) if mv_list else [],
            "nomore": no_more,
        }

    def tving_highlights(self, uparams=None, page="1"):
        mv_list, no_more = API.highlights(uparams=uparams, page=page)
        return {"list": self.tving_mv_parser(mv_list) if mv_list else [], "nomore": no_more}

    def tving_curation(self, code, uparams=None):
        url = f"/v2/media/movie/curation/{code}"
        params = {"pageNo": "1"}
        params.update(uparams or {})
        data = API.get(url, params=params)

        mv_list = [{"movie": x} for x in data["body"]["movies"]]
        no_more = data["body"]["has_more"].lower() != "y"
        return {"list": self.tving_mv_parser(mv_list) if mv_list else [], "nomore": no_more}

    def tving_category(self):
        url = "/v2/media/movie/categories"
        params = {
            "pageNo": "1",
            "pageSize": "10",
            "order": "new",
            "free": "y",
            "adult": "n",
            "guest": "all",
            "scope": "all",
        }
        data = API.get(url, params=params)
        return [
            {"code": x["category_code"], "name": x["category_name"]}
            for x in data["body"]["result"]
            if x["category_code"]
        ]
