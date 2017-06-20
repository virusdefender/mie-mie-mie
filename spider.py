import re
import requests
import time


class RequestFailed(Exception):
    pass


class Spider(object):
    def __init__(self, cookies):
        self.cookies = cookies

    @property
    def is_logged_in(self):
        # todo

        raise NotImplementedError()

    def _request(self, method, url, **kwargs):
        kwargs["timeout"] = 10

        if kwargs["headers"] is None:
            kwargs["headers"] = {}

        kwargs["headers"]["Cookie"] = self.cookies

        common_headers = {"Accept-Encoding": "gzip, deflate",
                          "Accept-Language": "en-US,en;q=0.8,zh;q=0.6,zh-CN;q=0.4",
                          "Cache-Control": "no-cache",
                          "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"}
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
    def get_over_view(self):
        resp = self.get("https://ad.toutiao.com/overture/data/overview/",
                        headers={"Accept": "application/json, text/javascript, */*; q=0.01",
                                 "Referer": "https://ad.toutiao.com/overture/data/campaign/ad/"})
        data = resp.json()
        if data["status"] != "success":
            print(data)
            raise requests.RequestException("Invalid response status")
        return resp.json()["data"]
    def get_ad_info(self, page, today_date, timestamp):
        url = "https://ad.toutiao.com/overture/data/ad_stat/?page=" + page + "&st=" + today_date + "&et=" + today_date + "&landing_type=0&status=no_delete&pricing=0&search_type=2&keyword=&sort_stat=&sort_order=1&_=" + timestamp
        resp = self.get(url,
                        headers={"Accept": "application/json, text/javascript, */*; q=0.01",
                                 "Referer": "https://ad.toutiao.com/overture/data/advertiser/ad/"})
        data = resp.json()
        return data

class YouYuanSpider(Spider):
    def get_channel_info(self, channel_id):
        resp = self.post("http://3.youyuan.com/sem/list",
                         data={"fromChannel": channel_id},
                         headers={"Content-Type": "application/x-www-form-urlencoded",
                                  "Referer": "http://3.youyuan.com/sem/list"})
        html = resp.text.replace(" ", "").replace("\r\n", "").replace("\t", "")
        regex = r"<tbody><tr><td>([0-9\-]+)</td><td>(\d+)</td><td>([0-9\.\-]+)</td><td>(\d+)</td><td>([0-9\.]+)</td><td>(\d+)</td><td>(\d+)</td></tr></tbody>"
        # regex = r"<tbody><tr><td>([0-9\-]+)</td><td>([0-9\.\-])</td><td>(\d+)</td><td>(\d+)</td><td>([0-9\.]+)</td><td>(\d+)</td><td>(\d+)</td></tr></tbody>"
        return re.compile(regex).findall(html)


if __name__ == "__main__":
    from config import *
    tou_tiao = TouTiaoSpider(tou_tiao_cookies[0])
    over_view = tou_tiao.get_over_view()

    channel_id_list = set()
    campaign_id_to_channel_id = {}

    for item in over_view["campaign_ads"]:
        campaign_id = item["campaign_id"]
        for ad in item["ads"]:
            try:
                channel_id_list.add(int(ad["ad_name"].split("-")[0]))
                campaign_id_to_channel_id[campaign_id] = int(ad["ad_name"].split("-")[0])
            except Exception as e:
                print(e, "invalid channel id", ad)
                exit(1)

    channel_id_to_toutiao_cost = {}

    for i in range(1, 100) :
        ad_info = tou_tiao.get_ad_info(page=str(i), today_date=str(time.strftime("%Y-%m-%d", time.localtime())), timestamp=str(time.time()))
        pagination = ad_info['data']['table']['pagination']
        ad_data = ad_info['data']['table']['ad_data']

        for item in ad_data :
            channel_id = item['ad_name'].split("-")[0]
            cost = float(item['stat_data']['stat_cost'])
            if channel_id_to_toutiao_cost.has_key(channel_id) :
                channel_id_to_toutiao_cost[channel_id] = channel_id_to_toutiao_cost[channel_id] + cost
            elif cost > 0.0:
                channel_id_to_toutiao_cost[channel_id] = cost

        if pagination['has_more'] == False:
            break

    print channel_id_to_toutiao_cost

    for key in channel_id_to_toutiao_cost :
        tou_tiao_cost = channel_id_to_toutiao_cost[key]
        channel_data = YouYuanSpider(you_yuan_cookie).get_channel_info(key)

        if len(channel_data) != 0 :
            regist_num = channel_data[0][3]
            arpu = channel_data[0][4]
            roi = float(arpu) * 1.8 / (float(tou_tiao_cost) / float(regist_num))
            print "======================================"
            print "arpu : ", arpu
            print "regist_num : ", regist_num
            print "tou_tiao_cost : ", tou_tiao_cost
            print "regist_num : ", regist_num
            print key, roi
            print "======================================"


