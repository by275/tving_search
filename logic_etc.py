from urllib.parse import parse_qs, quote

from flask import jsonify, render_template
from plugin import PluginModuleBase  # pylint: disable=import-error

from .logic_common import API
from .setup import P

logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting


class LogicETC(PluginModuleBase):
    def __init__(self, PM):
        super().__init__(PM, None)
        self.name = "etc"
        self.first_menu = "ratings"

    def process_menu(self, sub, req):
        _ = req
        arg = ModelSetting.to_dict()
        arg["package_name"] = package_name
        arg["module_name"] = self.name
        arg["bot_ktv_installed"] = True
        # pylint: disable=unused-import
        try:
            import bot_downloader_ktv
        except ImportError:
            arg["bot_ktv_installed"] = False

        try:
            if sub in ["ratings", "soon"]:
                return render_template(f"{package_name}_{self.name}_{sub}.html", arg=arg)
            return render_template(f"{package_name}_{self.name}.html", arg=arg, sub=sub)
        except Exception:
            logger.exception("Exception:")
            return render_template("sample.html", title=f"{package_name} - {self.name} - {sub}")

    def process_ajax(self, sub, req):
        try:
            p = req.form.to_dict() if req.method == "POST" else req.args.to_dict()
            if sub == "ratings":
                keyword = req.form["keyword"]
                return jsonify({"success": True, "data": self.get_daum_ratings(keyword)})
            if sub == "soon":
                return jsonify({"success": True, "data": API.prerelease()})
            if sub == "pop_whitelist_program":
                from bot_downloader_ktv import P as ktv_plugin  # pylint: disable=import-error

                whitelist_program = ktv_plugin.ModelSetting.get_list("vod_whitelist_program", "|")
                whitelist_program.remove(p.get("value", None))
                ktv_plugin.ModelSetting.set("vod_whitelist_program", " | ".join(whitelist_program))
                return jsonify({"success": True})
            raise NotImplementedError(f"잘못된 URL: {sub}")
        except Exception as e:
            logger.exception("Exception:")
            return jsonify({"success": False, "log": str(e)})

    def get_daum_ratings(self, keyword):
        from support_site import SiteDaum, SiteUtil

        url = f"https://search.daum.net/search?w=tot&q={quote(keyword)}"
        proxy_url = SiteDaum._proxy_url  # pylint: disable=protected-access
        cookies = SiteDaum._daum_cookie  # pylint: disable=protected-access
        root = SiteUtil.get_tree(url, proxy_url=proxy_url, headers=SiteDaum.default_headers, cookies=cookies)

        data = []
        for item in root.xpath('//*[@id="tcsColl"]//*[name()="c-card-view"]'):
            keywords = item.xpath('./*[@slot="keyword"]')[0].text_content().split()
            if not "#방송" in keywords or "#방영종료" in keywords:
                continue
            data_item = {"isScheduled": "#방영예정" in keywords}
            try:
                src_q = parse_qs(item.xpath('./*[@slot="image"]/@data-original-src')[0].split("?")[1])
                data_item["image"] = src_q["fname"][0]
            except Exception:
                data_item["image"] = "http://www.okbible.com/data/skin/okbible_1/images/common/noimage.gif"

            data_item["title"] = item.xpath('./*[@slot="title"]/text()')[0].strip()
            href_q = parse_qs(item.xpath('./*[@slot="title"]')[0].get("data-href").lstrip("?"))
            data_item["href"] = (
                "https://search.daum.net/search?"
                + f"w=tv&q={quote(href_q['q'][0])}&irk={href_q['irk'][0]}&irt=tv-program&DA=TVP"
            )

            for dt in item.xpath(".//dt"):
                dt_text = dt.text_content().strip()
                dd_text = dt.xpath("./following-sibling::dd")[0].text_content().strip()
                if dt_text == "편성":
                    data_item["air_time"] = dd_text
                elif dt_text == "시청률":
                    data_item["ratings"] = dd_text
                elif dt_text == "채널":
                    data_item["provider"] = dd_text

            data.append(data_item)

        data_with_ratings = [x for x in data if not x["isScheduled"] and x.get("ratings", "")]
        return (
            sorted(data_with_ratings, key=lambda x: float(x["ratings"].rstrip("%")), reverse=True)
            + [x for x in data if not x["isScheduled"] and not x.get("ratings", "")]
            + [x for x in data if x["isScheduled"]]
        )
