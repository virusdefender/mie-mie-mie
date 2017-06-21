# coding=utf-8
from __future__ import print_function, unicode_literals
import re
import requests
import time


class Spider(object):
    def __init__(self, cookies):
        self.cookies = cookies
        if not self.is_logged_in:
            print(self.__class__, "cookie is expired")
            exit(1)

    @property
    def is_logged_in(self):
        raise NotImplementedError()

    def _request(self, method, url, **kwargs):
        kwargs["timeout"] = 10

        if kwargs["headers"] is None:
            kwargs["headers"] = {}

        kwargs["headers"]["Cookie"] = self.cookies

        common_headers = {"Accept-Encoding": "gzip, deflate",
                          "Accept-Language": "en-US,en;q=0.8,zh;q=0.6,zh-CN;q=0.4",
                          "Cache-Control": "no-cache",
                          "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
                          "Referer": url}
        for k, v in common_headers.items():
            if k not in kwargs["headers"]:
                kwargs["headers"][k] = v
        retries = 3
        while True:
            try:
                r = requests.request(method, url, **kwargs)
                if r.status_code != 200:
                    raise requests.RequestException("Invalid status code [%d] when fetching url [%s]" % (r.status_code, url))
                return r
            except requests.RequestException:
                if retries == 0:
                    raise
                retries -= 1

    def get(self, url, headers=None):
        return self._request("get", url, headers=headers)

    def post(self, url, data, headers=None):
        return self._request("post", url, data=data, headers=headers)


class TouTiaoSpider(Spider):
    @property
    def is_logged_in(self):
        try:
            resp = self.get("https://ad.toutiao.com/overture/index/account_balance/")
            self.check_resp(resp.json())
            return True
        except requests.RequestException:
            return False

    def check_resp(self, data):
        if data["status"] != "success":
            print(data)
            raise requests.RequestException("Invalid response status")

    def get_ad_info(self, today_date):
        url = "https://ad.toutiao.com/overture/data/ad_stat/?page=1&st=" + \
              today_date + "&et=" + today_date + \
              "&landing_type=0&status=no_delete&pricing=0&search_type=2&keyword=&sort_stat=&sort_order=1&limit=1000"
        resp = self.get(url, headers={"Accept": "application/json, text/javascript, */*; q=0.01"})

        data = resp.json()
        self.check_resp(data)
        return data


class YouYuanSpider(Spider):
    @property
    def is_logged_in(self):
        resp = self.get("http://3.youyuan.com/index")
        return "<title>系统登录</title>" not in resp.text

    def get_channel_info(self, channel_id):
        resp = self.post("http://3.youyuan.com/sem/list",
                         data={"fromChannel": channel_id})
        html = resp.text.replace(" ", "").replace("\r\n", "").replace("\t", "")
        regex = r"<tbody><tr><td>([0-9\-]+)</td><td>(\d+)</td><td>([0-9\.\-]+)</td><td>(\d+)</td><td>([0-9\.]+)</td><td>(\d+)</td><td>(\d+)</td></tr></tbody>"
        return re.compile(regex).findall(html)


if __name__ == "__main__":
    from config import *
    you_yuan = YouYuanSpider(you_yuan_cookie)
    tou_tiao = TouTiaoSpider(tou_tiao_cookies[0])

    channel_cost = {}

    ad_info = tou_tiao.get_ad_info(today_date=time.strftime("%Y-%m-%d", time.localtime()))
    ad_data = ad_info["data"]["table"]["ad_data"]

    for item in ad_data:
        try:
            channel_id = item["ad_name"].split("-")[0]
        except ValueError:
            print("Invalid channel id", item["ad_name"])
            exit(1)
        cost = float(item["stat_data"]["stat_cost"])
        if channel_id in channel_cost :
            channel_cost[channel_id] = channel_cost[channel_id] + cost
        else:
            channel_cost[channel_id] = cost

    print("channel,", "arpu,", "reg_num,", "cost,", "roi")
    for key, cost in channel_cost.items():
        channel_data = you_yuan.get_channel_info(key)

        if channel_data:
            reg_num = float(channel_data[0][3])
            arpu = channel_data[0][4]
            if not (cost and reg_num):
                roi = -1
            else:
                roi = float(arpu) * 1.8 / (cost / reg_num)
            print(key, ",", arpu, ",", reg_num, ",", cost, ",", roi)
        else:
            print("get youyan channel", key, "failed, ignored")


