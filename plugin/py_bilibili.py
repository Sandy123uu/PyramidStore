# coding=utf-8
# !/usr/bin/python
import sys, os, json, threading, hashlib, time, random, re
from base.spider import Spider
from requests import session, utils, head
from requests.adapters import HTTPAdapter, Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import reduce
from urllib.parse import quote, unquote, urlencode, urlparse

dirname = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(dirname))
if dirname.startswith('/data/'):
    base_dir = os.path.dirname(os.path.dirname(dirname))
    dirname = os.path.join(base_dir, 'files')

class Spider(Spider):
    #默认设置
    defaultConfig = {
        'currentVersion': "20250425_1",
        #【建议通过扫码确认】设置Cookie，在双引号内填写
        'raw_cookie_line': "",
        #如果主cookie没有vip，可以设置第二cookie，仅用于播放会员番剧，所有的操作、记录还是在主cookie，不会同步到第二cookie
        'raw_cookie_vip': "",
        #主页默认显示20图
        'maxHomeVideoContent': '20',
        #收藏标签默认显示追番1，追剧2，默认收藏夹0
        'favMode': '0',
        #部分视频列表分页，限制每次加载数量
        'page_size': 12,
        #上传播放进度间隔时间，单位秒，b站默认间隔15，0则不上传播放历史
        'heartbeatInterval': '15',
        #视频默认画质ID
        'vodDefaultQn': '80',
        #视频默认解码ID
        'vodDefaultCodec': '7',
        #音频默认码率ID
        'vodDefaultAudio': '30280',
        #非会员播放会员专享视频时，添加一个页面可以使用解析源，解析源自行解决
        'bangumi_vip_parse': True,
        #付费视频添加一个页面可以使用解析，解析源自行解决
        'bangumi_pay_parse': True,
        #是否显示直播标签筛选中分区的细化标签, 0为不显示，1为显示
        'showLiveFilterTag': '1',
        #主页标签排序, 未登录或cookie失效时自动隐藏动态、收藏、关注、历史
        'cateManual': [
            "动态",
            "推荐",
            "影视",
            "直播",
            "收藏",
            "关注",
            "历史",
            "搜索",
        ],
        #自定义推荐标签的筛选
        'tuijianLis': [
            "热门",
            "排行榜",
            "每周必看",
            "入站必刷",
            "番剧时间表",
            "国创时间表"
        ],
        'rankingLis': [
            "影视",
            "动画",
            "游戏",
            "音乐",
            "知识",
            "科技",
            "生活",
            "美食",
            "动物",
            "运动",
            "舞蹈",
            "鬼畜",
            "娱乐",
            "汽车",
            "时尚",
        ],
    }

    #在动态标签的筛选中固定显示他，n为用户名或任意都可以，v必须为准确的UID
    focus_on_up_list = [
        #{"n":"电影最TOP", "v":"17819768"},
    ]

    #在搜索标签的筛选中固定显示搜索词
    focus_on_search_key = []

    def getName(self):
        return "哔哩哔哩"

    def load_config(self):
        try:
            with open(os.path.join(dirname, 'config.json'), encoding="utf-8") as f:
                self.userConfig = json.load(f)
            users = self.userConfig.get('users', {})
            if users.get('master') and users['master'].get('cookies_dic'):
                self.session_master.cookies = utils.cookiejar_from_dict(users['master']['cookies_dic'])
                self.userid = users['master']['userid']
            if users.get('fake') and users['fake'].get('cookies_dic'):
                self.session_fake.cookies = utils.cookiejar_from_dict(users['fake']['cookies_dic'])
        except:
            self.userConfig = {}
        self.userConfig = {**self.defaultConfig, **self.userConfig}

    dump_config_lock = threading.Lock()

    def dump_config(self):
        needSaveConfig = ['users', 'cateLive', 'cateManualLive', 'cateManualLiveExtra']
        userConfig_new = {}
        for key, value in self.userConfig.items():
            dafalutValue = self.defaultConfig.get(key)
            if dafalutValue != None and value != dafalutValue or key in needSaveConfig:
                userConfig_new[key] = value
        self.dump_config_lock.acquire()
        with open(os.path.join(dirname, 'config.json'), 'w', encoding="utf-8") as f:
            data = json.dumps(userConfig_new, indent=1, ensure_ascii=False)
            f.write(data)
        self.dump_config_lock.release()

    pool = ThreadPoolExecutor(max_workers=8)
    task_pool = []
    # 主页
    def homeContent(self, filter):
        self.pool.submit(self.add_live_filter)
        self.pool.submit(self.add_search_key)
        self.pool.submit(self.add_focus_on_up_filter)
        self.pool.submit(self.get_tuijian_filter)
        self.pool.submit(self.add_fav_filter)
        needLogin = ['动态', '收藏', '关注', '历史']
        cateManual = self.userConfig['cateManual']
        if not self.userid and not '登录' in cateManual:
            cateManual += ['登录']
        classes = []
        for k in cateManual:
            if k in needLogin and not self.userid:
                continue
            classes.append({
                'type_name': k,
                'type_id': k
            })
        result = {'class': classes}
        self.add_focus_on_up_filter_event.wait()
        self.add_live_filter_event.wait()
        self.add_fav_filter_event.wait()
        self.add_search_key_event.wait()
        if filter:
            result['filters'] = self.config['filter']
        self.pool.submit(self.dump_config)
        return result

    def destroy(self):
        pass

    # 用户cookies
    userid = csrf = ''
    session_master = session()
    session_vip = session()
    session_fake = session()
    con = threading.Condition()
    getCookie_event = threading.Event()
    retries = Retry(total=5,
                #status_forcelist=[ 500, 502, 503, 504 ],
                backoff_factor=0.1)
    adapter = HTTPAdapter(max_retries=retries)
    session_master.mount('https://', adapter)
    session_vip.mount('https://', adapter)
    session_fake.mount('https://', adapter)

    def getCookie_dosth(self, co):
        c = co.strip().split('=', 1)
        if not '%' in c[1]:
            c[1] = quote(c[1])
        return c

    def getCookie(self, _type='master'):
        raw_cookie = 'raw_cookie_line'
        if _type == 'vip':
            raw_cookie = 'raw_cookie_vip'
        raw_cookie = self.userConfig.get(raw_cookie)
        users = self.userConfig.get('users', {})
        user = users.get(_type, {})
        if not raw_cookie and not user:
            if _type == 'master':
                self.getCookie_event.set()
            with self.con:
                self.con.notifyAll()
            return
        cookies_dic = user.get('cookies_dic', {})
        if raw_cookie:
            cookies_dic = dict(map(self.getCookie_dosth, raw_cookie.split(';')))
        cookies = utils.cookiejar_from_dict(cookies_dic)
        url = 'https://api.bilibili.com/x/web-interface/nav'
        content = self.fetch(url, headers=self.header, cookies=cookies)
        res = json.loads(content.text)
        user['isLogin'] = 0
        if res["code"] == 0:
            user['isLogin'] = 1
            user['userid'] = res["data"]['mid']
            user['face'] = res['data']['face']
            user['uname'] = res['data']['uname']
            user['cookies_dic'] = cookies_dic
            user['isVIP'] = int(res['data']['vipStatus'])
            if _type == 'master':
                self.session_master.cookies = cookies
                self.userid = user['userid']
                self.csrf = cookies_dic['bili_jct']
            if user['isVIP']:
                self.session_vip.cookies = cookies
        else:
            self.userid = ''
        users[_type] = user
        with self.con:
            if len(user) > 1:
                self.userConfig.update({'users': users})
            if _type == 'master':
                self.getCookie_event.set()

    getFakeCookie_event = threading.Event()

    def getFakeCookie(self, fromSearch=None):
        if self.session_fake.cookies:
            self.getFakeCookie_event.set()
        header = {}
        header['User-Agent'] = self.header['User-Agent']
        rsp = self.fetch('https://space.bilibili.com/2/video', headers=header)
        self.session_fake.cookies = rsp.cookies
        self.getFakeCookie_event.set()
        with self.con:
            users = self.userConfig.get('users', {})
            users['fake'] = {'cookies_dic': dict(rsp.cookies)}
            self.userConfig.update({'users': users})
        if not fromSearch:
            self.getCookie_event.wait()
            if not self.session_master.cookies:
                self.session_master.cookies = rsp.cookies

    add_fav_filter_event = threading.Event()

    def add_fav_filter(self):
        users = self.userConfig.get('users', {})
        if users.get('master') and users['master'].get('userid'):
            userid = self.userConfig['users']['master']['userid']
        else:
            self.getCookie_event.wait()
            userid = self.userid
        fav_list = []
        if userid:
            url = 'https://api.bilibili.com/x/v3/fav/folder/created/list-all?up_mid=%s&jsonp=jsonp' % str(userid)
            jo = self._get_sth(url).json()
            if jo['code'] == 0 and jo.get('data'):
                fav = jo['data'].get('list')
                fav_list = list(map(lambda x:{'n': self.cleanCharacters(x['title'].strip()), 'v': x['id']}, fav))
        fav_top = [{"n": "追番", "v": "1"},{"n": "追剧", "v": "2"}]
        fav_config = self.config["filter"].get('收藏')
        if fav_config:
            fav_config.insert(0, {
                "key": "mlid",
                "name": "分区",
                "value": fav_top + fav_list,
            })
        self.add_fav_filter_event.set()
        self.userConfig["fav_list"] = fav_list

    add_focus_on_up_filter_event = threading.Event()

    def add_focus_on_up_filter(self):
        up_list = self.focus_on_up_list
        if not self.session_master.cookies:
            self.getCookie_event.wait()
        focus_on_up_list_mid = list(map(lambda x: x['v'], up_list))
        if self.session_master.cookies:
            url = 'https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/all?timezone_offset=-480&type=video&page=1'
            jo = self._get_sth(url).json()
            if jo['code'] == 0 and jo.get('data'):
                up = jo['data'].get('items', [])
                for u in map(lambda x: {'n': x['modules']["module_author"]['name'], 'v': str(x['modules']["module_author"]['mid'])}, up):
                    if not u in up_list and not u['v'] in focus_on_up_list_mid:
                        up_list.append(u)
        last_list = [{"n": "登录与设置", "v": "登录"}]
        up_list += last_list
        self.config["filter"]['动态'] = dynamic_config = [self.config["filter"].get('动态', [])[-1]]
        dynamic_config.insert(0, {
            "key": "mid",
            "name": "UP主",
            "value": up_list,
        })
        self.add_focus_on_up_filter_event.set()

    def get_live_parent_area_list(self, parent_area):
        name = parent_area['name']
        id = str(parent_area['id'])
        area = parent_area['list']
        area_dict = list(map(lambda area: {'n': area['name'], 'v': str(area['parent_id']) + '_' + str(area['id'])}, area))
        live_area = {'key': 'tid', 'name': name, 'value': area_dict}
        cateLive_name = {'id': id + '_0', 'value': live_area}
        return (name, cateLive_name)

    def get_live_list(self):
        url = 'https://api.live.bilibili.com/xlive/web-interface/v1/index/getWebAreaList?source_id=2'
        jo = self._get_sth(url, 'fake').json()
        if jo['code'] == 0:
            parent = jo['data']['data']
            self.userConfig['cateLive'] = dict(map(self.get_live_parent_area_list, parent))
        return self.userConfig['cateLive']

    def set_default_cateManualLive(self):
        cateManualLive = [{'n': '推荐', 'v': '推荐'},]
        for name in self.userConfig['cateLive']:
            area_dict = {'n': name, 'v': self.userConfig['cateLive'][name]['id']}
            cateManualLive.append(area_dict)
        self.defaultConfig['cateManualLive'] = cateManualLive
        return cateManualLive

    add_live_filter_event = threading.Event()

    def add_live_filter(self):
        cateLive = self.userConfig.get('cateLive', {})
        cateLive_task = self.pool.submit(self.get_live_list)
        if not cateLive:
            cateLive = cateLive_task.result()
        default_cateManualLive_task = self.pool.submit(self.set_default_cateManualLive)
        self.config["filter"]['直播'] = live_filter = []
        #分区栏
        cateManualLive = self.userConfig.get('cateManualLive', [])
        if not cateManualLive:
            cateManualLive = default_cateManualLive_task.result()
        if cateManualLive:
            live_area = {'key': 'tid', 'name': '分区', 'value': cateManualLive}
            live_filter.append(live_area)
        #显示分区细分
        if int(self.userConfig['showLiveFilterTag']):
            for name in cateLive.values():
                if len(name['value']['value']) > 1:
                    live_filter.append(name['value'])
        self.add_live_filter_event.set()

    add_search_key_event = threading.Event()

    def add_search_key(self):
        focus_on_search_key = self.focus_on_search_key
        url = 'https://api.bilibili.com/x/web-interface/search/square?limit=10&platform=web'
        jo = self._get_sth(url, 'fake').json()
        cateLive = {}
        if jo['code'] == 0:
            trending = jo['data']['trending'].get('list', [])
            focus_on_search_key += list(map(lambda x:x['keyword'], trending))
        keyword = {"key": "keyword", "name": "搜索词","value": []}
        keyword["value"] = list(map(lambda i: {'n': i, 'v': i}, focus_on_search_key))
        self.config["filter"]['搜索'] = search_filter = self.config["filter"]['搜索'][-3:]
        search_filter.insert(0, keyword)
        self.add_search_key_event.set()

    def get_tuijian_filter(self):
        tuijian_filter = {"番剧时间表": "10001", "国创时间表": "10004", "排行榜": "0", "动画": "1005", "游戏": "1008", "鬼畜": "1007", "音乐": "1003", "舞蹈": "1004", "影视": "1001", "娱乐": "1002", "知识": "1010", "科技": "1012", "生活": "160", "美食": "1020", "汽车": "1013", "时尚": "1014", "运动": "1018", "动物": "1024"}
        _dic = [{'n': 'tuijianLis', 'v': '分区'}, {'n': 'rankingLis', 'v': '排行榜'}]
        self.config["filter"]['推荐'] = filter_lis = []
        for d in _dic:
            _filter = {"key": "tid" ,'name': d['v'],"value": []}
            t_lis = self.userConfig.get(d['n'], [])
            for t in t_lis:
                tf = tuijian_filter.get(t)
                if not tf:
                    tf = t
                tf_dict = {'n': t, 'v': tf}
                _filter["value"].append(tf_dict)
            filter_lis.append(_filter)

    def __init__(self):
        self.load_config()
        self.pool.submit(self.getCookie)
        self.pool.submit(self.getFakeCookie)
        self.pool.submit(self.getCookie, 'vip')
        wts = round(time.time())
        hour = time.gmtime(wts).tm_hour
        self.pool.submit(self.get_wbiKey, hour)

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    # 降低内存占用
    def format_img(self, img):
        img += "@672w_378h_1c.webp"
        if not img.startswith('http'):
            img = 'https:' + img
        return img

    def pagination(self, array, pg):
        max_number = self.userConfig['page_size'] * int(pg)
        min_number = max_number - self.userConfig['page_size']
        return array[min_number:max_number]

    # 将超过10000的数字换成成以万和亿为单位
    def zh(self, num):
        if int(num) >= 100000000:
            p = round(float(num) / float(100000000), 1)
            p = str(p) + '亿'
        else:
            if int(num) >= 10000:
                p = round(float(num) / float(10000), 1)
                p = str(p) + '万'
            else:
                p = str(num)
        return p

    # 将秒数转化为 时分秒的格式
    def second_to_time(self, a):
        a = int(a)
        if a < 3600:
            result = time.strftime("%M:%S", time.gmtime(a))
        else:
            result = time.strftime("%H:%M:%S", time.gmtime(a))
        if str(result).startswith('0'):
            result = str(result).replace('0', '', 1)
        return result

    # 字符串时分秒以及分秒形式转换成秒
    def str2sec(self, x):
        x = str(x)
        try:
            h, m, s = x.strip().split(':')  # .split()函数将其通过':'分隔开，.strip()函数用来除去空格
            return int(h) * 3600 + int(m) * 60 + int(s)  # int()函数转换成整数运算
        except:
            m, s = x.strip().split(':')  # .split()函数将其通过':'分隔开，.strip()函数用来除去空格
            return int(m) * 60 + int(s)  # int()函数转换成整数运算

    # 提取番剧id
    def find_bangumi_id(self, url):
        aid = str(url).split('/')[-1]
        if not aid:
            aid = str(url).split('/')[-2]
        aid = aid.split('?')[0]
        return aid

    # 登录二维码
    def get_Login_qrcode(self, pg):
        result = {}
        if int(pg) != 1:
            return result
        video = [{
            "vod_id": 'setting_tab&filter',
            "vod_name": '标签与筛选',
            "vod_pic": 'https://www.bilibili.com/favicon.ico'
        },{
            "vod_id": 'setting_liveExtra',
            "vod_name": '查看直播细化标签',
            "vod_pic": 'https://www.bilibili.com/favicon.ico'
        }]
        url = 'https://passport.bilibili.com/x/passport-login/web/qrcode/generate'
        jo = self._get_sth(url, 'fake').json()
        if jo['code'] == 0:
            id = jo['data']['qrcode_key']
            url = jo['data']['url']
            account = {'master': '主账号', 'vip': '副账号'}
            isLogin = {0: '未登录', 1: '已登录'}
            isVIP = {0: '', 1: '👑'}
            users = self.userConfig.get('users', {})
            for _type, typeName in account.items():
                user = users.get(_type)
                if user:
                    video.append({
                        "vod_id": 'setting_login_' + id,
                        "vod_name": user['uname'],
                        "vod_pic": self.format_img(user['face']),
                        "vod_remarks": isVIP[user['isVIP']] + typeName + ' ' + isLogin[user['isLogin']]
                    })
            pic_url = {'data': url, 'quietzone': '208', 'codepage': 'UTF8', 'quietunit': 'px', 'errorcorrection': 'M', 'size': 'small'}
            video.append({
                "vod_id": 'setting_login_' + id,
                'vod_pic': 'http://jm92swf.s1002.xrea.com/?' + urlencode(pic_url),
            })
            video.append({
                "vod_id": 'setting_login_' + id,
                'vod_pic': 'https://bili.minggo.undo.it/API/QRCode?' + urlencode(pic_url),
            })
        result['list'] = video
        result['page'] = 1
        result['pagecount'] = 1
        result['limit'] = 1
        result['total'] = 1
        return result

    dynamic_offset = ''

    def get_dynamic(self, pg, mid, order):
        if mid == '0':
            result = {}
            if int(pg) == 1:
                self.dynamic_offset = ''
            url = 'https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/all?timezone_offset=-480&type=video&offset=%s&page=%s' % (self.dynamic_offset, pg)
            jo = self._get_sth(url).json()
            if jo['code'] == 0:
                self.dynamic_offset = jo['data'].get('offset')
                videos = []
                vodList = jo['data']['items']
                for vod in vodList:
                    up = vod['modules']["module_author"]['name']
                    ivod = vod['modules']['module_dynamic']['major']['archive']
                    aid = str(ivod['aid']).strip()
                    title = self.cleanCharacters(ivod['title'].strip())
                    img = ivod['cover'].strip()
                    # remark = str(ivod['duration_text']).strip()
                    remark = str(self.second_to_time(self.str2sec(ivod['duration_text']))).strip() + '  🆙' + str(
                        up).strip()  # 显示分钟数+up主名字
                    videos.append({
                        "vod_id": 'av' + aid,
                        "vod_name": title,
                        "vod_pic": self.format_img(img),
                        "vod_remarks": remark
                    })
                result['list'] = videos
                result['page'] = pg
                result['pagecount'] = 9999
                result['limit'] = 99
                result['total'] = 999999
            return result
        else:
            return self.get_up_videos(mid=mid, pg=pg, order=order)

    def get_found_vod(self, vod):
        aid = vod.get('aid', '')
        if not aid:
            aid = vod.get('id', '')
        goto = vod.get('goto', '')
        if not goto or goto and goto == 'av':
            aid = 'av' + str(aid).strip()
        elif goto == 'ad':
            return []
        title = vod['title'].strip()
        img = vod['pic'].strip()
        is_followed = vod.get('is_followed')
        if goto == 'live':
            room_info = vod['room_info']
            remark = ''
            live_status = room_info.get('live_status', '')
            if live_status:
                remark = '直播中  '
            else:
                return []
            remark += '👁' + room_info['watched_show']['text_small'] + '  🆙' + vod['owner']['name'].strip()
        else:
            rcmd_reason = vod.get('rcmd_reason', '')
            if rcmd_reason and type(rcmd_reason) == dict and rcmd_reason.get('content'):
                reason= '  🔥' + rcmd_reason['content'].strip()
                if '人气飙升' in reason:
                    reason= '  🔥人气飙升'
            elif is_followed:
                reason = '  已关注'
            else:
                #reason = "  💬" + self.zh(vod['stat']['danmaku'])
                reason = '  🆙' + vod['owner']['name'].strip()
            remark = str(self.second_to_time(vod['duration'])).strip() + "  ▶" + self.zh(vod['stat']['view']) + reason
        video = [{
            "vod_id": aid,
            "vod_name": title,
            "vod_pic": self.format_img(img),
            "vod_remarks": remark
        }]
        for v in map(self.get_found_vod, vod.get('others', [])):
            video.extend(v)
        return video

    _popSeriesInit = 0

    def get_found(self, tid, rid, pg):
        result = {}
        pagecount = 1
        if tid == '推荐':
            url = f"https://api.bilibili.com/x/web-interface/wbi/index/top/feed/rcmd?fresh_type=4&feed_version=V8&brush=1&fresh_idx={pg}&fresh_idx_1h={pg}&ps={self.userConfig['page_size']}"
            pagecount = 99
        elif tid == '热门':
            url = 'https://api.bilibili.com/x/web-interface/popular?pn={0}&ps={1}'.format(pg, self.userConfig['page_size'])
            pagecount = 99
        elif tid == "入站必刷":
            url = 'https://api.bilibili.com/x/web-interface/popular/precious'
        elif tid == "每周必看":
            if int(pg) == 1:
                url = 'https://api.bilibili.com/x/web-interface/popular/series/list'
                jo = self._get_sth(url, 'fake').json()
                self._popSeriesInit = int(jo['data']['list'][0]['number'])
            number = self._popSeriesInit - int(pg) + 1
            pagecount = self._popSeriesInit
            url = f'https://api.bilibili.com/x/web-interface/popular/series/one?number={number}'
        else:
            url = 'https://api.bilibili.com/x/web-interface/ranking/v2?rid={0}&type={1}'.format(rid, tid)
        jo = self._get_sth(url).json()
        if jo['code'] == 0:
            videos = []
            vodList = jo['data'].get('item')
            if not vodList: vodList = jo['data']['list']
            for v in map(self.get_found_vod, vodList):
                videos.extend(v)
            result['list'] = videos
            result['page'] = pg
            result['pagecount'] = pagecount
            result['limit'] = 99
            result['total'] = 999999
        return result

    def get_bangumi(self, tid, pg, order, season_status):
        result = {}
        if order == '追番剧':
            url = 'https://api.bilibili.com/x/space/bangumi/follow/list?type={0}&vmid={1}&pn={2}&ps={3}'.format(tid, self.userid, pg, self.userConfig['page_size'])
            jo = self._get_sth(url).json()
        else:
            url = 'https://api.bilibili.com/pgc/season/index/result?type=1&season_type={0}&page={1}&order={2}&season_status={3}&pagesize={4}'.format(tid, pg, order, season_status, self.userConfig['page_size'])
            if order == '热门':
                if tid == '1':
                    url = 'https://api.bilibili.com/pgc/web/rank/list?season_type={0}&day=3'.format(tid)
                else:
                    url = 'https://api.bilibili.com/pgc/season/rank/web/list?season_type={0}&day=3'.format(tid)
            jo = self._get_sth(url, 'fake').json()
        if jo['code'] == 0:
            if 'data' in jo:
                vodList = jo['data']['list']
            else:
                vodList = jo['result']['list']
            if len(vodList) > self.userConfig['page_size']:
                vodList = self.pagination(vodList, pg)
            videos = []
            for vod in vodList:
                aid = str(vod['season_id']).strip()
                title = vod['title']
                img = vod.get('ss_horizontal_cover')
                if not img:
                    if vod.get('first_ep_info') and 'cover' in vod['first_ep_info']:
                        img = vod['first_ep_info']['cover']
                    elif vod.get('first_ep') and 'cover' in vod['first_ep']:
                        img = vod['first_ep']['cover']
                    else:
                        img = vod['cover'].strip()
                remark = vod.get('index_show', '')
                if not remark and vod.get('new_ep') and vod['new_ep'].get('index_show'):
                    remark = vod['new_ep']['index_show']
                remark = remark.replace('更新至', '🆕')
                stat = vod.get('stat')
                if stat:
                    remark = '▶' + self.zh(stat.get('view')) + '  ' + remark
                videos.append({
                    "vod_id": 'ss' + aid,
                    "vod_name": title,
                    "vod_pic": self.format_img(img),
                    "vod_remarks": remark
                })
            result['list'] = videos
            result['page'] = pg
            result['pagecount'] = 9999
            result['limit'] = 90
            result['total'] = 999999
        return result

    def get_timeline(self, tid, pg):
        result = {}
        url = 'https://api.bilibili.com/pgc/web/timeline/v2?season_type={0}&day_before=2&day_after=4'.format(tid)
        jo = self._get_sth(url, 'fake').json()
        if jo['code'] == 0:
            videos1 = []
            vodList = jo['result']['latest']
            for vod in vodList:
                aid = str(vod['season_id']).strip()
                title = vod['title'].strip()
                img = vod['ep_cover'].strip()
                remark = '🆕' + vod['pub_index'] + '  ❤ ' + vod['follows'].replace('系列', '').replace('追番', '')
                videos1.append({
                    "vod_id": 'ss' + aid,
                    "vod_name": title,
                    "vod_pic": self.format_img(img),
                    "vod_remarks": remark
                })
            videos2 = []
            vodList2 = jo['result']['timeline']
            for i in range(len(vodList2)):
                vodList = vodList2[i]['episodes']
                for vod in vodList:
                    if str(vod['published']) == "0":
                        aid = str(vod['season_id']).strip()
                        title = str(vod['title']).strip()
                        img = str(vod['ep_cover']).strip()
                        date = str(time.strftime("%m-%d %H:%M", time.localtime(vod['pub_ts'])))
                        remark = date + "   " + vod['pub_index']
                        videos2.append({
                            "vod_id": 'ss' + aid,
                            "vod_name": title,
                            "vod_pic": self.format_img(img),
                            "vod_remarks": remark
                        })
            result['list'] = videos2 + videos1
            result['page'] = 1
            result['pagecount'] = 1
            result['limit'] = 90
            result['total'] = 999999
        return result

    def get_live(self, pg, parent_area_id, area_id):
        result = {}
        if parent_area_id == '推荐':
            url = 'https://api.live.bilibili.com/xlive/web-interface/v1/webMain/getMoreRecList?platform=web&page=%s' % pg
            jo = self._get_sth(url).json()
        else:
            url = 'https://api.live.bilibili.com/xlive/web-interface/v1/second/getList?platform=web&parent_area_id=%s&area_id=%s&sort_type=&page=%s' % (parent_area_id, area_id, pg)
            if parent_area_id == '热门':
                url = 'https://api.live.bilibili.com/room/v1/room/get_user_recommend?page=%s&page_size=%s' % (pg, self.userConfig['page_size'])
            jo = self._get_sth(url, 'fake').json()
        if jo['code'] == 0:
            videos = []
            vodList = jo['data']
            if 'recommend_room_list' in vodList:
                vodList = vodList['recommend_room_list']
            elif 'list' in vodList:
                vodList = vodList['list']
            for vod in vodList:
                aid = str(vod['roomid']).strip()
                title = self.cleanCharacters(vod['title'])
                img = vod.get('user_cover')
                if not img:
                    img = vod.get('cover')
                remark = '👁' + vod['watched_show']['text_small'].strip() + "  🆙" + vod['uname'].strip()
                videos.append({
                    "vod_id": aid,
                    "vod_name": title,
                    "vod_pic": self.format_img(img),
                    "vod_remarks": remark
                })
            result['list'] = videos
            result['page'] = pg
            result['pagecount'] = 9999
            result['limit'] = 99
            result['total'] = 999999
        return result

    def get_up_series(self, mid, pg):
        result = {}
        url = 'https://api.bilibili.com/x/polymer/web-space/seasons_series_list?mid=%s&page_num=%s&page_size=%s' % (mid, pg, self.userConfig['page_size'])
        jo = self._get_sth(url, 'fake').json()
        if jo['code'] == 0:
            videos = []
            jo = jo['data']['items_lists']
            vodList = jo['seasons_list'] + jo['series_list']
            for vod in vodList:
                meta = vod.get('meta')
                aid = str(meta.get('season_id', '')).strip()
                if aid:
                    aid = 'av' + str(vod['recent_aids'][0])
                else:
                    aid = 'list_' + str(mid) + '_series_' + str(meta.get('series_id', '')).strip()
                title = self.cleanCharacters(meta['name'])
                img = meta.get('cover')
                remark = meta.get('description', '').strip()
                videos.append({
                    "vod_id": aid,
                    "vod_name": title,
                    "vod_pic": self.format_img(img),
                    "vod_remarks": remark
                })
            result['list'] = videos
            result['page'] = pg
            result['pagecount'] = 9999
            result['limit'] = 99
            result['total'] = 999999
        return result

    get_up_videos_result = dict()

    def get_up_videos(self, mid, pg, order):
        result = {}
        if not mid in self.up_info or int(pg) == 1:
            self.get_up_info_event.clear()
            self.pool.submit(self.get_up_info, mid)
        get_access_id = self.pool.submit(self.get_wbiAccessID, mid)
        Space = order2 = ''
        if order == 'oldest':
            order2 = order
            order = 'pubdate'
        elif order == 'quicksearch':
            Space = '投稿: '
            videos = self.get_up_videos_result.get(mid, [])
            if videos:
                result['list'] = videos
                return result
        elif order == 'series':
            return self.get_up_series(mid=mid, pg=pg)
        tmp_pg = pg
        if order2:
            self.get_up_info_event.wait()
            tmp_pg = self.up_info[mid]['vod_pc'] - int(pg) + 1
        url = f"https://api.bilibili.com/x/space/wbi/arc/search?mid={mid}&pn={tmp_pg}&ps={self.userConfig['page_size']}&order={order}&web_location=1550101&w_webid={get_access_id.result()}"
        jo = self._get_sth(url, 'fake').json()
        videos = []
        if jo['code'] == 0:
            vodList = jo['data']['list']['vlist']
            for vod in vodList:
                aid = str(vod['aid']).strip()
                title = self.cleanCharacters(vod['title'].strip())
                img = vod['pic'].strip()
                remark = self.second_to_time(self.str2sec(str(vod['length']).strip())) + "  ▶" + self.zh(vod['play'])
                if not Space:
                    remark +=  "  💬" + self.zh(vod['video_review'])
                videos.append({
                    "vod_id": 'av' + aid,
                    "vod_name": Space + title,
                    "vod_pic": self.format_img(img),
                    "vod_remarks": remark
                })
            if order2:
                videos.reverse()
            if int(pg) == 1:
                self.get_up_info_event.wait()
                up_info = self.up_info[mid]
                vodname = up_info['name'] + "  个人主页"
                if Space:
                    vodname = 'UP: ' + up_info['name']
                gotoUPHome={
                    "vod_id": 'up' + str(mid),
                    "vod_name": vodname,
                    "vod_pic": self.format_img(up_info['face']),
                    "vod_remarks": up_info['following'] + '  👥' + up_info['fans'] + '  🎬' + str(up_info['vod_count'])
                }
                videos.insert(0, gotoUPHome)
            if Space:
                self.get_up_videos_result[mid] = videos
            result['list'] = videos
            result['page'] = pg
            result['pagecount'] = 99
            result['limit'] = 99
            result['total'] = 999999
        return result

    history_view_at = 0

    def get_history(self, type, pg):
        result = {}
        if int(pg) == 1:
            self.history_view_at = 0
        url = 'https://api.bilibili.com/x/web-interface/history/cursor?ps={0}&view_at={1}&type={2}'.format(self.userConfig['page_size'], self.history_view_at, type)
        if type == '稍后再看':
            url = 'https://api.bilibili.com/x/v2/history/toview'
        jo = self._get_sth(url).json()
        if jo['code'] == 0:
            videos = []
            vodList = jo['data'].get('list', [])
            if type == '稍后再看':
                vodList = self.pagination(vodList, pg)
            else:
                self.history_view_at = jo['data']['cursor']['view_at']
            for vod in vodList:
                history = vod.get('history', '')
                if history:
                    business = history['business']
                    aid = str(history['oid']).strip()
                    img = vod['cover'].strip()
                    part = str(history['part']).strip()
                else:
                    business = 'archive'
                    aid = str(vod["aid"]).strip()
                    img = vod['pic'].strip()
                    part = str(vod['page']['part']).strip()
                if business == 'article':
                    continue
                elif business == 'pgc':
                    aid = 'ep' + str(history['epid'])
                    _total = vod['total']
                    part = vod.get('show_title')
                elif business == 'archive':
                    aid = 'av' + aid
                    _total = vod['videos']
                title = self.cleanCharacters(vod['title'])
                if business == 'live':
                    live_status = vod.get('badge', '')
                    remark = live_status + '  🆙' + vod['author_name'].strip()
                else:
                    if str(vod['progress']) == '-1':
                        remark = '已看完'
                    elif str(vod['progress']) == '0':
                        remark = '刚开始看'
                    else:
                        process = str(self.second_to_time(vod['progress'])).strip()
                        remark = '看到  ' + process
                    if not _total in [0, 1] and part:
                        remark += ' (' + str(part) + ')'
                videos.append({
                    "vod_id": aid,
                    "vod_name": title,
                    "vod_pic": self.format_img(img),
                    "vod_remarks": remark
                })
            result['list'] = videos
            result['page'] = pg
            result['pagecount'] = 9999
            result['limit'] = 90
            result['total'] = 999999
        return result

    def get_fav_detail(self, pg, mlid, order):
        result = {}
        url = 'https://api.bilibili.com/x/v3/fav/resource/list?media_id=%s&order=%s&pn=%s&ps=10&platform=web&type=0' % (mlid, order, pg)
        jo = self._get_sth(url).json()
        if jo['code'] == 0:
            videos = []
            vodList = jo['data'].get('medias', [])
            for vod in vodList:
                # 只展示类型为 视频的条目
                # 过滤去掉收藏中的 已失效视频;如果不喜欢可以去掉这个 if条件
                if vod.get('type') in [2] and vod.get('title') != '已失效视频':
                    aid = str(vod['id']).strip()
                    title = self.cleanCharacters(vod['title'])
                    img = vod['cover'].strip()
                    remark = str(self.second_to_time(vod['duration'])).strip() + "  ▶" + self.zh(vod['cnt_info']['play']) + "　💬" + self.zh(vod['cnt_info']['danmaku'])
                    videos.append({
                        "vod_id": 'av' + aid + '_mlid' + str(mlid),
                        "vod_name": title,
                        "vod_pic": self.format_img(img),
                        "vod_remarks": remark
                    })
            result['list'] = videos
            result['page'] = pg
            result['pagecount'] = 9999
            result['limit'] = 99
            result['total'] = 999999
        return result

    def get_up_videoNum(self, mid):
        info={}
        url = f"http://api.bilibili.com/x/space/navnum?mid={mid}"
        jRoot = self._get_sth(url, 'fake').json()
        if jRoot['code'] == 0:
            info['vod_count'] = str(jRoot['data']['video']).strip()
            pc = divmod(int(info['vod_count']), self.userConfig['page_size'])
            vod_pc = pc[0]
            if pc[1] != 0:
                vod_pc += 1
            info['vod_pc'] = vod_pc
        self.up_info[mid].update(info)
        self.get_up_info_event.set()

    get_up_info_event = threading.Event()
    up_info = {}

    def get_up_info(self, mid, data={}):
        self.up_info[mid] = info = self.up_info.get(mid, {})
        self.pool.submit(self.get_up_videoNum, mid)
        if not data:
            url = f"https://api.bilibili.com/x/web-interface/card?mid={mid}"
            jRoot = self._get_sth(url).json()
            if jRoot['code'] == 0:
                data = jRoot['data']
            else:
                return info
        jo = data['card']
        info['following'] = '未关注'
        if data['following']:
            info['following'] = '已关注'
        info['name'] = name = self.cleanCharacters(jo['name'])
        info['crname'] = '[a=cr:{"id": "' + mid + '_pubdate_getupvideos","name": "' + name.replace('"', '\\"') + '"}/]' + name + '[/a]'
        info['face'] = jo['face']
        info['fans'] = self.zh(jo['fans'])
        info['like_num'] = self.zh(data['like_num'])
        info['desc'] = jo['Official']['desc'] + "　" + jo['Official']['title']
        return info

    def get_vod_relation(self, query):
        url = f'https://api.bilibili.com/x/web-interface/archive/relation?{query}'
        jo = self._get_sth(url).json()
        relation = []
        if jo['code'] == 0:
            jo = jo['data']
            if jo['attention']:
                relation.append('已关注')
            else:
                relation.append('未关注')
            triple = []
            if jo['favorite']:
                triple.append('⭐')
            if jo['like']:
                triple.append('👍')
            coin = jo.get('coin')
            if coin:
                triple.append('💰'*coin)
            if len(triple) == 3:
                relation.append('👍💰⭐')
            else:
                relation.extend(triple)
            if jo['dislike']:
                relation.append('👎')
            if jo['season_fav']:
                relation.append('已订阅合集')
        return relation

    def get_follow(self, pg, sort):
        result = {}
        if sort == "最常访问":
            url = 'https://api.bilibili.com/x/relation/followings?vmid={0}&pn={1}&ps=10&order=desc&order_type=attention' .format(self.userid, pg)
        elif sort == "最近关注":
            url = 'https://api.bilibili.com/x/relation/followings?vmid={0}&pn={1}&ps=10&order=desc&order_type='.format(self.userid, pg)
        elif sort == "正在直播":
            url = 'https://api.live.bilibili.com/xlive/web-ucenter/v1/xfetter/GetWebList?page={0}&page_size=10'.format(pg)
        elif sort == "最近访问":
            url = 'https://api.bilibili.com/x/v2/history?pn={0}&ps=15'.format(pg)
        elif sort == "特别关注":
            url = 'https://api.bilibili.com/x/relation/tag?mid={0}&tagid=-10&pn={1}&ps=10'.format(self.userid, pg)
        elif sort == "悄悄关注":
            url = 'https://api.bilibili.com/x/relation/whispers?pn={0}&ps=10'.format(pg)
        else:
            url = 'https://api.bilibili.com/x/relation/followers?vmid={0}&pn={1}&ps=10&order=desc&order_type=attention'.format(self.userid, pg)
        jo = self._get_sth(url).json()
        if jo['code'] != 0:
            return result
        if sort == "特别关注" or sort == "最近访问":
            vodList = jo['data']
        elif sort == "正在直播":
            vodList = jo['data']['rooms']
        else:
            vodList = jo['data']['list']
        if int(pg) == 1:
            self.recently_up_list = []
        follow = []
        for f in vodList:
            remark = ''
            if sort == "最近访问":
                mid = 'up' + str(f['owner']['mid'])
                if mid in self.recently_up_list:
                    continue
                self.recently_up_list.append(mid)
                title = str(f['owner']['name']).strip()
                img = str(f['owner']['face']).strip()
            elif sort == "正在直播":
                mid = str(f['room_id'])
                title = self.cleanCharacters(f['title'])
                img = f['cover_from_user'].strip()
                remark = f['uname'].strip()
            else:
                mid = 'up' + str(f['mid'])
                title = str(f['uname']).strip()
                img = str(f['face']).strip()
            if 'special' in f and f['special'] == 1:
                remark = '特别关注'
            follow.append({
                "vod_id": mid,
                "vod_name": title,
                "vod_pic": self.format_img(img),
                "vod_remarks": remark
            })
        result['list'] = follow
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = 99
        result['total'] = 999999
        return result

    def homeVideoContent(self):
        videos = self.get_found(rid='0', tid='all', pg=1)['list'][:int(self.userConfig['maxHomeVideoContent'])]
        result = {'list': videos}
        return result

    def categoryContent(self, tid, pg, filter, extend):
        self.pool.submit(self.stop_heartbeat)
        if tid == "推荐":
            if 'tid' in extend:
                tid = extend['tid']
            if tid.isdigit():
                tid = int(tid)
                if tid > 10000:
                    tid -= 10000
                    return self.get_timeline(tid=tid, pg=pg)
                rid = tid
                tid = 'all'
                return self.get_found(tid=tid, rid=rid, pg=pg)
            rid = '0'
            return self.get_found(tid=tid, rid=rid, pg=pg)
        elif tid == "影视":
            tid = '1'
            order = '热门'
            season_status = '-1'
            if 'tid' in extend:
                tid = extend['tid']
            if 'order' in extend:
                order = extend['order']
            if 'season_status' in extend:
                if order == '热门':
                    order = '2'
                season_status = extend['season_status']
            return self.get_bangumi(tid, pg, order, season_status)
        elif tid == "动态":
            mid = '0'
            order = 'pubdate'
            if 'mid' in extend:
                mid = extend['mid']
            if 'order' in extend:
                order = extend['order']
            if mid == '0' and not self.userid or mid == '登录':
                return self.get_Login_qrcode(pg)
            return self.get_dynamic(pg=pg, mid=mid, order=order)
        elif tid == '直播':
            tid = "热门"
            area_id = '0'
            if 'tid' in extend:
                tid = extend['tid']
            if '_' in tid:
                tids = tid.split('_')
                tid = tids[0]
                area_id = tids[1]
            return self.get_live(pg=pg, parent_area_id=tid, area_id=area_id)
        elif tid == "登录":
            return self.get_Login_qrcode(pg)
        elif tid == "关注":
            sort = "最常访问"
            if 'sort' in extend:
                sort = extend['sort']
            return self.get_follow(pg, sort)
        elif tid == "收藏":
            mlid = str(self.userConfig['favMode'])
            if 'mlid' in extend:
                mlid = extend['mlid']
            fav_config = self.config["filter"].get('收藏')
            if mlid in ['1', '2']:
                return self.get_bangumi(tid=mlid, pg=pg, order='追番剧', season_status='')
            elif mlid == '0' and fav_config:
                for i in fav_config:
                    if i['key'] == 'mlid':
                        if len(i['value']) > 1:
                            mlid = i['value'][2]['v']
                        break
            order = 'mtime'
            if 'order' in extend:
                order = extend['order']
            return self.get_fav_detail(pg=pg, mlid=mlid, order=order)
        elif tid == '历史':
            type = 'all'
            if 'type' in extend:
                type = extend['type']
            if type == 'UP主':
                return self.get_follow(pg=pg, sort='最近访问')
            return self.get_history(type=type, pg=pg)
        elif tid.endswith('_getbangumiseasons'):
            if int(pg) == 1:
                return {'list': self.detailContent_args[tid.split('_')[0]]['seasons']}
        elif tid.endswith('_getupvideos'):
            mid, order, clicklink = tid.split('_')
            return self.get_up_videos(pg=pg, mid=mid, order=order)
        elif tid.endswith('_related'):
            aid, clicklink = tid.split('_')
            url = f'https://api.bilibili.com/x/web-interface/archive/related?aid={aid}'
            jo = self._get_sth(url, 'master').json()
            result = {}
            if jo.get('code') == 0:
                videos = []
                for v in map(self.get_found_vod, jo['data']):
                    videos.extend(v)
                result['list'] = videos
                result['page'] = 1
                result['pagecount'] = 1
                result['limit'] = 99
                result['total'] = 40
            return result
        elif tid.endswith('_clicklink'):
            keyword = tid.replace('_clicklink', '')
            duration_diff = '0'
            if 'duration' in extend:
                duration_diff = extend['duration']
            return self.get_search_content(key=keyword, pg=pg, duration_diff=duration_diff, order='', type='video', ps=self.userConfig['page_size'])
        else:
            duration_diff = '0'
            if 'duration' in extend:
                duration_diff = extend['duration']
            type = 'video'
            if 'type' in extend:
                type = extend['type']
            order = 'totalrank'
            if 'order' in extend:
                order = extend['order']
            keyword = str(self.search_key)
            search_config = self.config["filter"].get('搜索')
            if not keyword and search_config:
                for i in search_config:
                    if i['key'] == 'keyword':
                        if len(i['value']) > 0:
                            keyword = i['value'][0]['v']
                        break
            if 'keyword' in extend:
                keyword = extend['keyword']
            return self.get_search_content(key=keyword, pg=pg, duration_diff=duration_diff, order=order, type=type, ps=self.userConfig['page_size'])

    def get_search_content(self, key, pg, duration_diff, order, type, ps):
        value = None
        if not str(pg).isdigit():
            value = pg
            pg = 1
        query = dict(keyword=key, page=pg, duration=duration_diff, order=order, search_type=type, page_size=ps)
        url = f'https://api.bilibili.com/x/web-interface/wbi/search/type'
        jo = self._get_sth(url, 'fake', queryDict=query).json()
        result = {}
        if jo.get('code') == 0 and 'result' in jo['data']:
            videos = []
            vodList = jo['data'].get('result')
            if vodList and type == 'live':
                vodList = vodList.get('live_room')
            if not vodList:
                return result
            for vod in vodList:
                if type != vod['type']:
                    continue
                title = ''
                if type == 'bili_user':
                    aid = 'up' + str(vod['mid']).strip()
                    img = vod['upic'].strip()
                    remark = '👥' + self.zh(vod['fans']) + "  🎬" + self.zh(vod['videos'])
                    title = vod['uname']
                elif type == 'live':
                    aid = str(vod['roomid']).strip()
                    img = vod['cover'].strip()
                    remark = '👁' + self.zh(vod['online'])  + '  🆙' + vod['uname']
                elif 'media' in type:
                    aid = 'ss' + str(vod['season_id']).strip()
                    img = vod['cover'].strip()
                    remark = str(vod['index_show']).strip().replace('更新至', '🆕')
                else:
                    aid = 'av' + str(vod['aid']).strip()
                    img = vod['pic'].strip()
                    remark = str(self.second_to_time(self.str2sec(vod['duration']))).strip() + "  ▶" + self.zh(vod['play'])
                    if value == None:
                        remark += "  💬" + self.zh(vod['danmaku'])
                if not title:
                    title = self.cleanCharacters(vod['title'])
                if value:
                    title = value + title
                videos.append({
                    "vod_id": aid,
                    "vod_name": title,
                    "vod_pic": self.format_img(img),
                    "vod_remarks": remark
                })
            result['list'] = videos
            result['page'] = pg
            result['pagecount'] = 9999
            result['limit'] = 99
            result['total'] = 999999
        return result

    def cleanSpace(self, s): return str(s).replace('\n', '').replace('\t', '').replace('\r', '').replace(' ', '')

    def cleanCharacters(self, s): return str(s).replace("<em class=\"keyword\">", "").replace("</em>", "").replace("&quot;",'"').replace('&amp;', '&')

    def get_normal_episodes(self, episode):
        this_array = episode.get('this_array')
        array = self.detailContent_args
        if this_array:
            array = array[this_array]
        aid = episode.get('aid', '')
        if not aid:
            aid = array['aid']
        cid = episode.get('cid', '')
        ep_title = episode.get('title', '')
        if not ep_title:
            ep_title = episode.get('part', '')
        duration = episode.get('duration', '')
        if not duration:
            page = episode.get('page', '')
            if page:
                duration = page['duration']
        badge = long_title = preview = parse = ''
        epid = episode.get('ep_id', '')
        if 'redirect_url' in episode and 'bangumi' in episode['redirect_url']:
            epid = self.find_bangumi_id(episode['redirect_url'])
        if epid:
            if duration and str(duration).endswith('000'):
                duration = int(duration / 1000)
            if ep_title.isdigit():
                ep_title = '第' + ep_title + array['title_type']
            badge = episode.get('badge', '')
            if not self.session_vip.cookies and badge == '会员' and self.userConfig['bangumi_vip_parse'] or badge == '付费' and self.userConfig['bangumi_pay_parse']:
                array['parse'] = parse = '1'
            if self.session_vip.cookies:
                badge = badge.replace('会员', '')
            if badge == '预告':
                badge = badge.replace('预告', '')
                preview = '1'
            if badge:
                badge = '【' + badge + '】'
            long_title = episode.get('long_title', '')
            if not badge and long_title:
                long_title = ' ' + long_title
        title = ep_title + badge + long_title
        title = title.replace("#", "﹟").replace("$", "﹩")
        if 'ugc_season' in array:
            if title in array['ugc_season']:
                title += f'_av{aid}'
            else:
                array['ugc_season'].append(title)
        url = f"{title}${aid}_{cid}_{epid}_{duration}_"
        if this_array:
            url += '@' + this_array
        if f'{aid}_{cid}' in array:
            pages = array['pages']
            pages[0] = url + '@thisepisode@'
            url = '#'.join(pages)
            array['pages'] = pages
        fromep = array.get('epid', '')
        if fromep == 'ep' + str(epid):
            array['fromep'] = url
        ssid = array.get('ssid', '')
        if ssid:
            if preview:
                return url, ''
            if parse:
                if long_title:
                    long_title = '【解析】' + long_title
                ep_title += long_title
                parseurl = f"{ep_title}${aid}_{cid}_{epid}_{duration}_{parse}"
                if this_array:
                    parseurl += '@' + this_array
                if fromep == 'ep' + str(epid):
                    array['fromep'] = parseurl + '#' + array['fromep']
            else:
                parseurl = url
            return url, parseurl
        else:
            return url

    def get_ugc_season(self, section, season_title, sec_len, array):
        if sec_len > 1:
            sec_title = season_title + ' ' + section['title']
        else:
            sec_title = season_title
        sec_title = sec_title.replace("#", "﹟").replace("$", "﹩")
        episodes = section.get('episodes')
        playUrl = '#'.join(map(self.get_normal_episodes, map(lambda e: self.add_this_array(e, array), episodes)))
        if '@thisepisode@' in playUrl:
            playUrl = playUrl.replace('@thisepisode@', '')
            return sec_title, playUrl, 0
        return sec_title, playUrl

    def get_vodReply(self, oid, pg=''):
        url = f'https://api.bilibili.com/x/v2/reply/wbi/main?type=1&ps=30&oid={oid}'
        jRoot = self._get_sth(url).json()
        result = ''
        if jRoot['code'] == 0:
            replies = jRoot['data'].get('replies')
            top_replies = jRoot['data'].get('top_replies')
            if top_replies and replies:
                replies = top_replies + replies
            if replies:
                up_mid = jRoot['data']['upper']['mid']
                ReplyList = []
                for r in replies:
                    rpid = r['rpid']
                    sex = r['member']['sex']
                    if sex and sex == '女':
                        sex = '👧'
                    else:
                        sex = '👦'
                    mid = r['mid']
                    name = r['member']['uname']
                    if mid == up_mid:
                        name = '🆙' + name
                    like = '👍' + self.zh(r['like'])
                    name = '[a=cr:{"id": "' + f'{mid}_pubdate_getupvideos","name": "' + name.replace('"', '\\"') + '"}/]' + like + sex + name + '[/a]' + '：'
                    message = r['content']['message'].strip()
                    if r'/note-app/' in message:
                        continue
                    if len(message) > 400 or message.count('n') > 24:
                        message = self.cleanSpace(message)
                    jump_url = r['content'].get('jump_url', {})
                    for key, values in jump_url.items():
                        origKey = key
                        if not values.get('app_url_schema') and not values.get('pc_url'):
                            if key.startswith('https://www.bilibili.com/') or key.startswith('https://b23.tv/'):
                                key = str(key).split('?')[0].split('/')
                                while key[-1] == '':
                                    key.pop(-1)
                                key = key[-1]
                            if key.startswith('av') or key.startswith('BV') or key.startswith('ep') or key.startswith('ss'):
                                rpid = str(r['rpid'])
                                title = values['title'].replace('"', '\\"')
                                realName = '[a=cr:{"id": "' + key + '_clicklink","name": "' + title + '"}/]' + '▶' +title + '[/a]'
                                message = message.replace(origKey, realName)
                    content = name + message
                    ReplyList.append(content)
                result = '\n'.join(ReplyList)
        return result

    def add_this_array(self, e, array):
        e['this_array'] = array
        return e

    detailContent_args = {}

    def detailContent(self, array):
        self.pool.submit(self.stop_heartbeat)
        array = array[0]
        if array.startswith('setting'):
            aids = array.split('_')
            if aids[1] == 'tab&filter':
                return self.setting_tab_filter_detailContent()
            elif aids[1] == 'liveExtra':
                return self.setting_liveExtra_detailContent()
            elif aids[1] == 'login':
                return self.setting_login_detailContent(aids[2])
        if array.startswith('list'):
            return self.series_detailContent(array)
        if array.isdigit():
            return self.live_detailContent(array)
        if array.startswith('up'):
            return self.up_detailContent(array)
        self.detailContent_args[array] = this_array = {'this_array': array, **self.detailContent_args.get(array, {})}
        graph_version = this_array.get('graph_version')
        if graph_version:
            return self.interaction_detailContent(this_array)
        _notfirst = id = mlid = query = ''
        aid = this_array.get('aid')
        epid = this_array.get('epid')
        if aid:
            array = f'av{aid}'
            if epid:
                array = epid
            _notfirst = 1
        this_array['_notfirst'] = _notfirst
        if array.startswith('ss') or array.startswith('ep'):
            return self.ysContent(this_array)
        for i in array.split('_'):
            if i.startswith('av'):
                id = i.replace('av', '')
                query = f'aid={id}'
            elif i.startswith('BV'):
                id = i
                query = f'bvid={i}'
            elif i.startswith('mlid'):
                mlid = i.replace('mlid', '')
        if not 'vodReply' in this_array:
            this_array['vodReply'] = self.pool.submit(self.get_vodReply, id)
        if not 'relation' in this_array:
            this_array['relation'] = self.pool.submit(self.get_vod_relation, query)
        url = f'https://api.bilibili.com/x/web-interface/wbi/view/detail?{query}'
        jRoot = self._get_sth(url, 'fake').json()
        if jRoot['code'] != 0:
            return {}
        jo = jRoot['data']['View']
        redirect_url = jo.get('redirect_url', '')
        if 'bangumi' in redirect_url:
            this_array['epid'] = id = self.find_bangumi_id(redirect_url)
            return self.ysContent(this_array)
        array = this_array['this_array']
        mid = str(jo['owner']['mid'])
        this_array['aid'] = aid = str(jo.get('aid'))
        cid = jo.get('cid')
        if not 'up_info' in this_array:
            this_array['up_info'] = self.pool.submit(self.get_up_info, mid=mid, data=jRoot['data'].get('Card'))
        #正片
        title = self.cleanCharacters(jo['title'])
        pic = jo['pic']
        desc = jo['desc'].strip()
        typeName = jo['tname']
        date = time.strftime("%Y%m%d", time.localtime(jo['pubdate']))  # 投稿时间本地年月日表示
        stat = jo['stat']
        _is_stein_gate = jo['rights'].get('is_stein_gate', 0)
        # 演员项展示视频状态，包括以下内容：
        remark = []
        remark.append('▶' + self.zh(stat['view']))
        remark.append('💬' + self.zh(stat['danmaku']))
        remark.append('👍' + self.zh(stat['like']))
        remark.append('💰' + self.zh(stat['coin']))
        remark.append('⭐' + self.zh(stat['favorite']))
        vod = {
            "vod_id": 'av' + str(aid),
            "vod_name": title, 
            "vod_pic": pic,
            "type_name": typeName,
            "vod_year": date,
        }
        vod['vod_remarks'] = "　".join(remark)
        if f'{aid}_{cid}' in this_array:
            this_array.pop(f'{aid}_{cid}')
        pages = jo['pages']
        if pages:
            this_array['pages'] = list(map(self.get_normal_episodes, map(lambda e: self.add_this_array(e, array), pages)))
        AllPt = []
        AllPu = []
        #相关合集
        save_args = []
        task_pool = []
        ugc_season = jo.get('ugc_season')
        if ugc_season:
            this_array['ugc_season'] = []
            this_array[f'{aid}_{cid}'] = ''
            sections = ugc_season['sections']
            for section in sections:
                t = self.pool.submit(self.get_ugc_season, section, ugc_season['title'], len(sections), array)
                task_pool.append(t)
            for t in as_completed(task_pool):
                if t.result()[-1] == 0:
                    AllPt.insert(0, t.result()[0])
                    AllPu.insert(0, t.result()[1])
                    if not '#' in t.result()[1]:
                        _notfirst = 1
                else:
                    AllPt.append(t.result()[0])
                    AllPu.append(t.result()[1])
                task_pool.remove(t)
            save_args.append('aid')
            if not _notfirst:
                save_args += ['vodReply', 'relation', 'up_info', f'{aid}_{cid}']
        else:
            AllPt = ['视频分集']
            if _is_stein_gate:
                AllPt[0] = '互动视频'
        if not ugc_season or not _notfirst:
            if pages:
                AllPt = [AllPt[0]]
                playUrl = '#'.join(this_array['pages']).replace('@thisepisode@', '')
                AllPu = [playUrl]
        if self.userid:
            #做点什么
            follow = f'➕关注${aid}_{mid}__1__notplay_follow'
            unfollow = f'➖取关${aid}_{mid}__2__notplay_follow'
            like = f'👍点赞${aid}_{mid}__1__notplay_like'
            unlike = f'👍🏻取消点赞${aid}_{mid}__2__notplay_like'
            coin1 = f'👍💰投币${aid}_{mid}__1__notplay_coin'
            coin2 = f'👍💰💰${aid}_{mid}__2__notplay_coin'
            triple = f'👍💰⭐三连${aid}_{mid}____notplay_triple'
            secondPList = [follow, triple, like, coin1, coin2, unfollow, unlike]
            if mlid:
                favdel = f'☆取消收藏${aid}_{mid}__{mlid}_del_notplay_fav'
                secondPList.insert(0, favdel)
            for fav in self.userConfig.get("fav_list", []):
                folder = fav['n'].replace("#", "﹟").replace("$", "﹩")
                ids = fav['v']
                fav = f'⭐{folder}${aid}_{mid}__{ids}_add_notplay_fav'
                secondPList.insert(0, fav)
            secondP = '#'.join(secondPList)
            AllPt.insert(1, '做点什么')
            AllPu.insert(1, secondP)
        if _is_stein_gate:
            AllPu[0] = '片头$' + AllPu[0].split('$')[1]
        vod['vod_play_from'] = "$$$".join(AllPt)
        vod['vod_play_url'] = "$$$".join(AllPu)
        if not ugc_season or _notfirst:
            vod_content = ['[a=cr:{"id": "' + str(aid) + '_related","name":"' + title.replace('"', '\\"') + '"}/]相关推荐[/a]']
            if len(desc) < 60 and desc.count('n') < 4:
                desc += '\n' * int(3 - len(desc) / 29)
            vod_content.append(desc)
            vod_tags = '；'.join(sorted(map(lambda x: '[a=cr:{"id": "' + x['tag_name'].replace('"', '\\"') + '_clicklink","name":"' + x['tag_name'].replace('"', '\\"') + '"}/]' + '﹟' + x['tag_name'] + '﹟' + '[/a]', jRoot['data'].get('Tags', [])), key=len))
            vod_content.append(vod_tags)
            #视频关系
            up_info = this_array.get('up_info')
            relation = this_array.get('relation')
            if up_info and relation:
                up_info = up_info.result()
                vod['vod_director'] = '🆙 ' + up_info['crname'] + '　👥 ' + up_info['fans'] + '　' + '　'.join(relation.result())
            vodReply = this_array.get('vodReply')
            if vodReply:
                vod_content.append(vodReply.result())
            vod['vod_content'] = '\n'.join(vod_content)
            if _is_stein_gate:
                this_array['AllPt'] = AllPt.copy()
                this_array['AllPu'] = AllPu.copy()
                this_array['vod_list'] = vod.copy()
                save_args += ['aid', 'AllPt', 'AllPu', 'vod_list']
        if not ugc_season and not _is_stein_gate:
            self.detailContent_args.pop(array)
        else:
            _dc_args = {}
            for x, y in this_array.items():
                if x in save_args:
                    _dc_args[x] = y
            self.detailContent_args[array] = _dc_args.copy()
        result = {
            'list': [
                vod
            ]
        }
        return result

    def interaction_detailContent(self, array):
        this_array = array.get('this_array')
        aid = array.get('aid')
        cid = array.get('cid', 0)
        edgeid = array.get('edgeid', 0)
        graph_version = array.get('graph_version')
        url = f'https://api.bilibili.com/x/stein/edgeinfo_v2?aid={aid}&graph_version={graph_version}&edge_id={edgeid}'
        data = self._get_sth(url, 'fake').json().get('data')
        result = {}
        if data:
            AllPt = array.get('AllPt').copy()
            AllPu = array.get('AllPu').copy()
            vod = array.get('vod_list')
            if edgeid:
                title = str(data['title']).replace("#", "﹟").replace("$", "﹩")
                AllPu[0] += f'#{title}${aid}_{cid}___@{this_array}'
            else:
                AllPu[0] = AllPu[0].split('#')[0]
            array['AllPu'] = AllPu.copy()
            questions = data['edges'].get('questions', [])
            playUrl = []
            for q in questions:
                q_title = q.get('title', '')
                for c in q.get('choices', []):
                    c_edgeid = c['id']
                    c_cid = c['cid']
                    option = c.get('option', '')
                    title = ' '.join([q_title, option]).replace("#", "﹟").replace("$", "﹩")
                    playUrl.append(f'{title}${c_edgeid}_{c_cid}_interaction@{this_array}')
            if playUrl:
                AllPt.insert(1, '选项')
                AllPu.insert(1, '#'.join(playUrl))
            else:
                array.pop('edgeid')
                array.pop('cid')
            vod['vod_play_from'] = "$$$".join(AllPt)
            vod['vod_play_url'] = "$$$".join(AllPu)
            result['list'] = [vod]
        return result

    def series_detailContent(self, array):
        mid, type, sid = array.replace('list_', '').split('_')
        pg = 1
        ps = 99
        vod = {"vod_id": array, 'vod_play_from': 'B站'}
        urlL = []
        while True:
            url = 'https://api.bilibili.com/x/series/archives?mid=%s&series_id=%s&pn=%s&ps=%s' % (mid, sid, pg, ps)
            jo = self._get_sth(url, 'fake').json()
            data = jo.get('data')
            if not vod.get("vod_name"):
                vod["vod_name"] = data['archives'][0]['title']
            playUrl = '#'.join(map(self.get_normal_episodes, data.get('archives')))
            urlL.append(playUrl)
            total = data['page']['total']
            if (ps * pg) >= total:
                break
            pg += 1
        vod['vod_play_url'] = '#'.join(urlL)
        up_info = self.up_info[mid]
        vod['vod_director'] = '🆙 ' + up_info['name'] + "　" + up_info['following']
        result = {
            'list': [
                vod
            ]
        }
        return result

    def up_detailContent(self, array):
        mid = array.replace('up', '')
        self.get_up_info_event.clear()
        self.pool.submit(self.get_up_info, mid)
        follow = f'关注$_{mid}__1__notplay_follow'
        unfollow = f'取消关注$_{mid}__2__notplay_follow'
        spfollow = f'特别关注$_{mid}__-10_special_notplay_follow'
        unspfollow = f'取消特别关注$_{mid}__0_special_notplay_follow'
        doWhat = [follow, spfollow, unfollow, unspfollow]
        doWhat = '做点什么$ $$$' + '#'.join(doWhat)
        self.get_up_info_event.wait()
        up_info = self.up_info[mid]
        vod = {
            "vod_name": up_info['name'] + "  个人主页",
            "vod_pic": up_info['face'],
            "vod_director": '🆙 ' + up_info['name'] + "　" + up_info['following'] + '　UID：' + str(mid),
            "vod_remarks": "👥 " + up_info['fans'] + "　🎬 " + up_info['vod_count'] + "　👍 " + up_info['like_num'],
            "vod_content": up_info['desc']
        }
        if self.userid:
            vod['vod_play_from'] = '做点什么$$$关注TA'
            vod['vod_play_url'] = doWhat
        tabfilter = self.config['filter'].get('动态')
        vod["vod_actor"] = ' '.join(map(lambda x: '[a=cr:{"id": "' + str(mid) + '_' + x['v'] +'_getupvideos","name": "' + up_info['name'].replace('"', '\\"') + '  ' + x['n'] + '"}/]' + x['n'] + '[/a]', tabfilter[-1]['value']))
        result = {
            'list': [
                vod
            ]
        }
        return result

    def setting_login_detailContent(self, key):
        cookie_dic_tmp = self.cookie_dic_tmp.get(key, '')
        message = ''
        if not cookie_dic_tmp:
            message = self.get_cookies(key)
        if message:
            message = f"【{message}】通过手机客户端扫码确认登录后点击相应按钮设置账号"
        else:
            message = '【已扫码并确认登录】请点击相应按钮设置当前获取的账号为：'
        vod = {
            "vod_name": "登录与设置",
            "vod_content": '通过手机客户端扫码并确认登录后，点击相应按钮设置cookie，设置后不需要管嗅探结果，直接返回二维码页面刷新，查看是否显示已登录，已登录即可重新打开APP以加载全部标签',
        }
        vod_play_from = ['登录$$$退出登录']
        vod_play_url = []
        first = message + '$ '
        login = '设置为主账号，动态收藏关注等内容源于此$' + str(key) + '_master_login_setting'
        login_vip = '设置为备用的VIP账号，仅用于播放会员番剧$' + str(key) + '_vip_login_setting'
        vod_play_url.append('#'.join([first, login, login_vip]))
        second = '点击相应按钮退出账号>>>$ '
        logout = '退出主账号$master_logout_setting'
        logout_vip = '退出备用的VIP账号$vip_logout_setting'
        vod_play_url.append('#'.join([second, logout, logout_vip]))
        cate_lis = [{
            'f': '主页站点推荐栏',
            'c': 'maxHomeVideoContent',
            'd': {
                '3': '3图',
                '4': '4图',
                '5': '5图',
                '6': '6图',
                '8': '8图',
                '9': '9图',
                '10': '10图',
                '20': '20图',
            }
        },{
            'f': '视频画质',
            'c': 'vodDefaultQn',
            'd': self.vod_qn_id
        },{
            'f': '视频编码',
            'c': 'vodDefaultCodec',
            'd': self.vod_codec_id
        },{
            'f': '音频码率',
            'c': 'vodDefaultAudio',
            'd': self.vod_audio_id
        },{
            'f': '收藏默认显示',
            'c': 'favMode',
            'd': {
                '0': '默认收藏夹',
                '1': '追番',
                '2': '追剧',
            }
        },{

            'f': '上传播放进度',
            'c': 'heartbeatInterval',
            'd': {
                '0': '关',
                '15': '开',
            }
        },{

            'f': '直播筛选细化',
            'c': 'showLiveFilterTag',
            'd': {
                '0': '关',
                '1': '开',
            }
        }]
        for cate in cate_lis:
            vod_play_from.append(cate['f'])
            defaultConfig = cate['d'][str(int(self.userConfig[cate['c']]))]
            if 'vodDefaultAudio' == cate['c']:
                defaultConfig = str(defaultConfig).replace('000', 'k')
            url = ['当前：' + defaultConfig + '$ ']
            for id, name in cate['d'].items():
                if 'vodDefaultAudio' == cate['c']:
                    name = str(name).replace('000', 'k')
                url.append(name + '$' + str(id) + '_' + cate['c'] + '_setting')
            vod_play_url.append('#'.join(url))
        vod['vod_play_from'] = '$$$'.join(vod_play_from)
        vod['vod_play_url'] = '$$$'.join(vod_play_url)
        result = {
            'list': [
                vod
            ]
        }
        return result

    def setting_tab_filter_detailContent(self):
        vod = {
            "vod_name": "标签与筛选",
            "vod_content": '依次点击各标签，同一标签第一次点击为添加，第二次删除，可以返回到二维码页后重进本页查看预览，最后点击保存，未选择的将追加到末尾，如果未保存就重启app，将丢失未保存的配置',
        }
        vod_play_from = []
        vod_play_url = []
        cate_lis = [
            {'n': 'cateManual', 'v': '标签'},
            {'n': 'tuijianLis', 'v': '推荐[分区]'},
            {'n': 'rankingLis', 'v': '推荐[排行榜]'},
            {'n': 'cateManualLive', 'v': '直播'},
        ]
        for cate in cate_lis:
            _List = cate['n']
            vod_play_from.append(cate['v'])
            List_tmp = self.userConfig.get(str(_List) + '_tmp', [])
            status = ''
            if List_tmp:
                status = '【未保存】'
            else:
                List_tmp = self.userConfig.get(_List, [])
            if not List_tmp:
                List_tmp = self.defaultConfig.get(_List)
            if List_tmp and type(List_tmp[0]) == dict:
                List_tmp = list(map(lambda x:x['n'], List_tmp))
            url = ['当前: ' + ','.join(List_tmp) + '$ ', f"{status}点击这里保存$_{_List}_save_setting", f"点击这里恢复默认并保存$_{_List}_clear_setting"]
            defaultConfig = self.defaultConfig[_List].copy()
            if _List == 'cateManualLive':
                extra_live_filter = self.userConfig.get('cateManualLiveExtra', [])
                defaultConfig.extend(extra_live_filter.copy())
            for name in defaultConfig:
                value = str(name)
                if type(name) == dict:
                    value = name['n'] + '@@@' + name['v'].replace('_', '@@@')
                    name = name['n']
                url.append(f"{name}${value}_{_List}_setting")
            vod_play_url.append('#'.join(url))
        vod['vod_play_from'] = '$$$'.join(vod_play_from)
        vod['vod_play_url'] = '$$$'.join(vod_play_url)
        result = {
            'list': [
                vod
            ]
        }
        return result

    def setting_liveExtra_detailContent(self):
        vod = {
            "vod_name": "查看直播细化标签",
            "vod_content": '点击想要添加的标签，同一标签第一次点击为添加，第二次删除，完成后在[标签与筛选]页继续操作，以添加到直播筛选分区列中',
        }
        vod_play_from = ['已添加']
        cateManualLiveExtra = self.userConfig.get('cateManualLiveExtra', [])
        vod_play_url = ['点击相应标签(只)可以删除$ #清空$clear_liveFilter_setting']
        for name in cateManualLiveExtra:
            value = name['v']
            name = name['n']
            vod_play_url.append(name + '$' + 'del_' + name + '_' + value + '_liveFilter_setting')
        vod_play_url = ['#'.join(vod_play_url)]
        cateLive = self.userConfig.get('cateLive', {})
        for parent, parent_dic in cateLive.items():
            area_dic = parent_dic['value']['value']
            if len(area_dic) == 1:
                continue
            vod_play_from.append(parent)
            url = []
            for area in area_dic:
                name = str(area['n']).replace('_', '-').replace("#", "﹟").replace("$", "﹩")
                id = str(area['v']).replace('_', '@@@').replace("#", "﹟").replace("$", "﹩")
                url.append(name + '$add_' + name + '_' + id + '_liveFilter_setting')
            vod_play_url.append('#'.join(url))
        vod['vod_play_from'] = '$$$'.join(vod_play_from)
        vod['vod_play_url'] = '$$$'.join(vod_play_url)
        result = {
            'list': [
                vod
            ]
        }
        return result

    def get_all_season(self, season):
        season_id = str(season['season_id'])
        season_title = season['season_title']
        this_array = self.detailContent_args[season['this_array']]
        if season_id == this_array['ssid']:
            this_array['s_title'] = season_title
        pic = season['cover']
        remark = season['new_ep']['index_show']
        result = {
            "vod_id": 'ss' + season_id,
            "vod_name": season_title,
            "vod_pic": self.format_img(pic),
            "vod_remarks": remark}
        return result

    def get_bangumi_section(self, section, array):
        sec_title = section['title'].replace("#", "﹟").replace("$", "﹩")
        sec_type = section['type']
        if sec_type in [1, 2] and len(section['episode_ids']) == 0:
            episodes = section['episodes']
            playUrl = list(map(lambda x: self.get_normal_episodes(x)[0], map(lambda e: self.add_this_array(e, array), episodes)))
            return (sec_title, playUrl)

    def ysContent(self, this_array):
        array = this_array['this_array']
        aid = this_array.get('aid')
        epid = this_array.get('epid')
        if epid:
            array = epid
            this_array.pop('epid')
        if 'ep' in array:
            aid = 'ep_id=' + array.replace('ep', '')
            this_array['epid'] = array
        else:
            aid = 'season_id=' + array.replace('ss', '')
        array = this_array['this_array']
        url = "https://api.bilibili.com/pgc/view/web/season?{0}".format(aid)
        jo = self._get_sth(url, 'fake').json().get('result', {})
        this_array['ssid'] = ssid = str(jo['season_id'])
        title = jo['title']
        this_array['s_title'] = jo['season_title']
        this_array['title_type'] = '集'
        if jo['type'] in [1, 4]:
            this_array['title_type'] = '话'
        remark = jo['new_ep']['desc']
        if 'rating' in jo:
            remark = str(jo['rating']['score']) + '分  ' + remark
        #添加系列到搜索
        seasons = jo.get('seasons')
        if len(seasons) == 1:
            this_array['s_title'] = seasons[0]['season_title']
            seasons = 0
        elif len(seasons) > 1:
            this_array['seasons'] = list(map(self.get_all_season, map(lambda e: self.add_this_array(e, array), seasons)))
            remark += '  [a=cr:{"id": "' + array + '_getbangumiseasons","name": "' + title.replace('"', '\\"') + '"}/]更多系列[/a]'
        #获取正片
        episodes = jo.get('episodes')
        #获取花絮
        section_task = []
        for s in jo.get('section', []):
            if s:
                t = self.pool.submit(self.get_bangumi_section, s, array)
                section_task.append(t)
        pic = jo['cover']
        typeName = jo['share_sub_title']
        date = jo['publish']['pub_time'][0:4]
        dec = jo['evaluate']
        stat = jo['stat']
        # 演员和导演框展示视频状态，包括以下内容：
        status = "▶" + self.zh(stat['views']) + "　❤" + self.zh(stat['favorites'])
        vod = {
            "vod_id": 'ss' + ssid,
            "vod_name": title,
            "vod_pic": pic,
            "type_name": typeName,
            "vod_year": date,
            "vod_actor": status,
            "vod_content": dec
        }
        vod["vod_remarks"] = remark
        PreviewPu = []
        fromL = []
        urlL = []
        if episodes:
            FirstPu = []
            ParsePu = []
            for x, y in map(self.get_normal_episodes, map(lambda e: self.add_this_array(e, array), episodes)):
                if y:
                    FirstPu.append(x)
                    ParsePu.append(y)
                else:
                    PreviewPu.append(x)
            if this_array.get('parse') and ParsePu:
                fromL.append(str(this_array['s_title']) + '【解析】')
                urlL.append('#'.join(ParsePu))
            if FirstPu:
                fromL.append(str(this_array['s_title']))
                urlL.append('#'.join(FirstPu))
        sectionF = []
        sectionU = []
        for t in as_completed(section_task):
            s = t.result()
            if s:
                if s[0] == '预告':
                    PreviewPu += s[1]
                else:
                    sectionF.append(s[0])
                    sectionU.append('#'.join(s[1]))
        if PreviewPu:
            fromL.append('预告')
            urlL.append('#'.join(PreviewPu))
        fromL += sectionF
        urlL += sectionU
        fromep = this_array.get('fromep')
        if fromep:
            fromL.insert(0, 'B站')
            urlL.insert(0, fromep)
        if self.userid:
            ZhuiPf = '追番剧'
            ZhuiPu = f'❤追番剧$__{ssid}_add__notplay_zhui#💔取消追番剧$__{ssid}_del__notplay_zhui'
            fromL.insert(1, ZhuiPf)
            urlL.insert(1, ZhuiPu)
        vod['vod_play_from'] = '$$$'.join(fromL)
        vod['vod_play_url'] = '$$$'.join(urlL)
        result = {
            'list': [
                vod
            ]
        }
        return result

    def get_live_api2_playurl(self, room_id):
        playFrom = []
        playUrl = []
        url = 'https://api.live.bilibili.com/xlive/web-room/v2/index/getRoomPlayInfo?room_id={0}&qn=0&platform=web&protocol=0,1&format=0,1,2&codec=0,1&dolby=5&panorama=1'.format(room_id)
        jo = self._get_sth(url, 'vip').json()
        if jo['code'] == 0:
            playurl_info = jo['data'].get('playurl_info', '')
            if playurl_info:
                stream = playurl_info['playurl']['stream']
                liveDic = {
                    'codec': {'avc': '0', 'hevc': '1'},
                    'format': {'flv': '0', 'ts': '1', 'fmp4': '2'},
                }
                liveDic['qn'] = dict(map(lambda x:(x['qn'], x['desc']), playurl_info['playurl']['g_qn_desc']))
                vodList = []
                for i in stream:
                    vodList.extend(i['format'])
                api2_playUrl = {}
                for v in vodList:
                    format = str(v.get('format_name'))
                    for c in v['codec']:
                        codec = str(c.get('codec_name'))
                        accept_qn = c.get('accept_qn')
                        for qn in accept_qn:
                            url = format + '_' + codec + f"$live_{room_id}_" + str(qn) + '_' + liveDic['format'][format] + '_' + liveDic['codec'][codec]
                            if not api2_playUrl.get(liveDic['qn'][qn]):
                                api2_playUrl[liveDic['qn'][qn]] = []
                            api2_playUrl[liveDic['qn'][qn]].append(url)
                for key, value in api2_playUrl.items():
                    playFrom.append(key)
                    playUrl.append('#'.join(value))
        result = playFrom, playUrl
        return result

    def live_detailContent(self, room_id):
        get_live_api2_playurl = self.pool.submit(self.get_live_api2_playurl, room_id)
        url = "https://api.live.bilibili.com/room/v1/Room/get_info?room_id=" + str(room_id)
        jRoot = self._get_sth(url, 'fake').json()
        result = {}
        if jRoot.get('code') == 0:
            jo = jRoot['data']
            mid = str(jo["uid"])
            up_info = self.pool.submit(self.get_up_info, mid)
            title = self.cleanCharacters(jo['title'])
            pic = jo.get("user_cover")
            desc = jo.get('description')
            typeName = jo.get('parent_area_name') + '-' + jo.get('area_name')
            vod = {
                "vod_id": room_id,
                "vod_name": title,
                "vod_pic": pic,
                "type_name": typeName,
                "vod_content": desc,
            }
            if int(jo.get('live_status')):
                 vod['vod_year'] = jo.get('live_time').replace('-', '.')
            playFrom = get_live_api2_playurl.result()[0]
            playUrl = get_live_api2_playurl.result()[1]
            if self.userid:
                secondF = '关注TA'
                first = '是否关注$ '
                follow = f'➕关注$_{mid}__1__notplay_follow'
                unfollow = f'➖取关$_{mid}__2__notplay_follow'
                secondPList = [first, follow, unfollow]
                secondP = '#'.join(secondPList)
                playFrom.insert(1, secondF)
                playUrl.insert(1, secondP)
            vod['vod_play_from'] = '$$$'.join(playFrom)
            vod['vod_play_url'] = '$$$'.join(playUrl)
            up_info = up_info.result()
            vod["vod_director"] = '🆙 ' + up_info['crname']  + "　👥 " + self.zh(jo.get('attention')) + '　' + up_info['following']
            result['list'] = [vod]
        return result

    search_key = ''

    def searchContent(self, key, quick, pg="1"):
        if not self.session_fake.cookies:
            self.pool.submit(self.getFakeCookie, True)
        if int(pg) > 1:
            return self.get_search_content(key = key, pg = pg, duration_diff = 0, order = '', type = 'video', ps = self.userConfig['page_size'])
        task_pool = []
        self.search_key = key
        types = {'video': '','media_bangumi': '番剧: ', 'media_ft': '影视: ', 'bili_user': '用户: ', 'live': '直播: '}
        for type, value in types.items():
            t = self.pool.submit(self.get_search_content, key = key, pg = value, duration_diff = 0, order = '', type = type, ps = self.userConfig['page_size'])
            task_pool.append(t)
        result = {}
        vodList = []
        for t in as_completed(task_pool):
            res = t.result().get('list', [])
            vodList.extend(res)
            task_pool.remove(t)
        if len(vodList):
            result['list'] = vodList
            result['page'] = pg
            result['pagecount'] = 9999
            result['limit'] = 99
            result['total'] = 999999
        return result

    stop_heartbeat_event = threading.Event()

    def stop_heartbeat(self):
        try:
            for t in self.task_pool:
                t.cancel()
                self.task_pool.remove(t)
        finally:
            self.stop_heartbeat_event.set()

    def start_heartbeat(self, aid, cid, ssid, epid, duration, played_time):
        heartbeatInterval = int(self.userConfig['heartbeatInterval'])
        if not self.userid or not heartbeatInterval:
            return
        heartbeat_times = int((duration - played_time) / heartbeatInterval) + 1
        url = 'https://api.bilibili.com/x/click-interface/web/heartbeat'
        data = {'aid': str(aid), 'cid': str(cid), 'csrf': str(self.csrf)}
        if ssid:
            data['sid'] = str(ssid)
            data['epid'] = str(epid)
            data['type'] = '4'
        heartbeat_count = 0
        self.stop_heartbeat_event.clear()
        while True:
            if heartbeat_count == heartbeatInterval or self.stop_heartbeat_event.is_set():
                played_time += heartbeat_count
                heartbeat_count = 0
            if not heartbeat_count:
                heartbeat_times -= 1
                if not heartbeat_times:
                    #播完为-1
                    played_time = -1
                    self.stop_heartbeat_event.set()
                data['played_time'] = str(played_time)
                data = self.encrypt_wbi(**data)[1]
                self.pool.submit(self._post_sth, url=url, data=data)
                if self.stop_heartbeat_event.is_set():
                    break
            time.sleep(1)
            heartbeat_count += 1

    wbi_key = {}
    def get_wbiKey(self, hour):
        r = self.fetch("https://api.bilibili.com/x/web-interface/nav", headers=self.header)
        wbi_img_url = r.json()['data']['wbi_img']['img_url']
        wbi_sub_url = r.json()['data']['wbi_img']['sub_url']
        oe = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12,
            38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62,
            11, 36, 20, 34, 44, 52]
        ae = wbi_img_url.split("/")[-1].split(".")[0] + wbi_sub_url.split("/")[-1].split(".")[0]
        le = reduce(lambda s, i: s + ae[i], oe, "")[:32]
        self.wbi_key = {
            "key": le,
            "hour": hour
        }

    def get_wbiAccessID(self, uid: str):
        info = self.up_info.get(uid, {})
        access_id = info.get("access_id")
        access_id_ts = info.get("access_id_ts")
        wts = round(time.time())
        if access_id and access_id_ts < wts:
            return access_id
        text = self.fetch(f"https://space.bilibili.com/{uid}/dynamic", headers=self.header).text
        __RENDER_DATA__ = re.search(
            r"<script id=\"__RENDER_DATA__\" type=\"application/json\">(.*?)</script>",
            text,
            re.S,
        ).group(1)
        info["access_id"] = access_id = json.loads(unquote(__RENDER_DATA__))["access_id"]
        info["access_id_ts"] = wts + 86395
        self.up_info[uid].update(info)
        return access_id

    def encrypt_wbi(self, **params):
        wts = round(time.time())
        hour = time.gmtime(wts).tm_hour
        if not self.wbi_key or hour != self.wbi_key['hour']:
            self.get_wbiKey(hour)
        params["wts"] = wts
        dm_rand = 'ABCDEFGHIJK'
        params["dm_img_list"] = '[]'
        params["dm_img_str"] = ''.join(random.sample(dm_rand, 2))
        params["dm_cover_img_str"] = ''.join(random.sample(dm_rand, 2))
        params["dm_img_inter"] = '{"ds":[],"wh":[0,0,0],"of":[0,0,0]}'
        params = dict(sorted(params.items()))
        params = {k : ''.join(filter(lambda chr: chr not in "!'()*", str(v))) for k, v in params.items()}
        Ae = urlencode(params)
        w_rid = hashlib.md5((Ae + self.wbi_key['key']).encode(encoding='utf-8')).hexdigest()
        params['w_rid'] = w_rid
        return [Ae + "&w_rid=" + w_rid, params]

    def _get_sth(self, url, _type='master', headers=None, queryDict={}, **kwargs):
        if not queryDict:
            query = urlparse(url).query
            queryDict = {k: v for param in query.split('&') if query for k, v in [param.split('=', 1)]} if query else {}
        url = url.split('?')[0] + '?' + self.encrypt_wbi(**queryDict)[0]
        print(url)
        if headers is None:
            headers = self.header
        if _type == 'vip' and self.session_vip.cookies:
            rsp = self.session_vip.get(url, headers=headers, **kwargs)
        elif _type == 'fake':
            if not self.session_fake.cookies:
                self.getFakeCookie_event.wait()
            rsp = self.session_fake.get(url, headers=headers, **kwargs)
        else:
            rsp = self.session_master.get(url, headers=headers, **kwargs)
        return rsp

    def _post_sth(self, url, data):
        return self.session_master.post(url, headers=self.header, data=data)

    def post_live_history(self, room_id):
        data = {'room_id': str(room_id), 'platform': 'pc', 'csrf': str(self.csrf)}
        url = 'https://api.live.bilibili.com/xlive/web-room/v1/index/roomEntryAction'
        self._post_sth(url=url, data=data)

    def do_notplay(self, ids):
        aid, mid, ssid, arg0, arg1, this, what= ids
        data = {'csrf': str(self.csrf)}
        doShare = url = ''
        if what == 'follow':
            if arg1 == 'special':
                data.update({'fids': str(mid), 'tagids': str(arg0)})
                url = 'https://api.bilibili.com/x/relation/tags/addUsers'
            else:
                data.update({'fid': str(mid), 'act': str(arg0)})
                url = 'https://api.bilibili.com/x/relation/modify'
        elif what == 'zhui':
            data.update({'season_id': str(ssid)})
            url = 'https://api.bilibili.com/pgc/web/follow/' + str(arg0)
        elif what == 'like':
            data.update({'aid': str(aid), 'like': str(arg0)})
            url = 'https://api.bilibili.com/x/web-interface/archive/like'
        elif what == 'coin':
            data.update({'aid': str(aid), 'multiply': str(arg0), 'select_like': '1'})
            url = 'https://api.bilibili.com/x/web-interface/coin/add'
        elif what == 'fav':
            data.update({'rid': str(aid), 'type': '2'})
            data[arg1 + '_media_ids'] = str(arg0)
            url = 'https://api.bilibili.com/x/v3/fav/resource/deal'
        elif what == 'triple':
            data.update({'aid': str(aid)})
            url = 'https://api.bilibili.com/x/web-interface/archive/like/triple'
        self._post_sth(url=url, data=data)
        if what in ['like', 'coin', 'fav', 'triple']:
            data = {'aid': str(aid), 'csrf': str(self.csrf), 'csrf_token': str(self.csrf)}
            url = 'https://api.bilibili.com/x/web-interface/share/add'
            self.pool.submit(self._post_sth, url=url, data=data)
        self._refreshDetail()

    def get_cid(self, aid, cid):
        url = f'https://api.bilibili.com/x/web-interface/view?aid={aid}&cid={cid}'
        jo = self._get_sth(url).json().get('data', {})
        if not cid:
            cid = jo['cid']
        dur = jo['duration']
        epid = ''
        if 'redirect_url' in jo and 'bangumi' in jo['redirect_url']:
            epid = self.find_bangumi_id(jo['redirect_url'])
        return cid, dur, epid

    cookie_dic_tmp = {}

    def get_cookies(self, key):
        url = 'https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key=' + key
        jo = self._get_sth(url, 'fake').json()
        if jo['code'] == 0:
            message = jo['data']['message']
            if not message:
                self.cookie_dic_tmp[key] = dict(self.session_fake.cookies)
                self.pool.submit(self.getFakeCookie)
            return message
        return '网络错误'

    def set_cookie(self, key, _type):
        cookie_dic_tmp = self.cookie_dic_tmp.get(key, '')
        if not cookie_dic_tmp:
            message = self.get_cookies(key)
            if message:
                return
        users = self.userConfig.get('users', {})
        users[_type] = {'cookies_dic': self.cookie_dic_tmp.get(key, {})}
        self.userConfig.update({'users': users})
        self.getCookie(_type)
        self.dump_config()

    def unset_cookie(self, _type):
        if _type == 'vip':
            self.session_vip.cookies.clear()
        else:
            self.session_master.cookies = self.session_fake.cookies
            self.userid = self.csrf = ''
        if _type in self.userConfig.get('users', {}):
            self.userConfig['users'].pop(_type)
            self.dump_config()

    def set_normal_default(self, id, type):
        self.userConfig[type] = str(id)
        self.dump_config()

    def set_normal_cateManual(self, name, _List, action):
        List_tmp = self.userConfig.get(str(_List) + '_tmp')
        if not List_tmp:
            List_tmp = self.userConfig[str(_List) + '_tmp'] = []
        if action == 'save':
            for _item in self.defaultConfig[_List]:
                if not _item in List_tmp.copy():
                    self.userConfig[str(_List) + '_tmp'].append(_item)
            self.userConfig[_List] = self.userConfig[str(_List) + '_tmp'].copy()
            self.userConfig.pop(_List + '_tmp')
            self.dump_config()
        elif action == 'clear':
            self.userConfig[_List] = self.defaultConfig[_List].copy()
            self.userConfig.pop(str(_List) + '_tmp')
            self.dump_config()
        else:
            if _List == 'cateManualLive':
                name = name.split('@@@')
                if len(name) == 3:
                    name[1] += '_' + str(name[2])
                name = {'n': name[0], 'v': str(name[1])}
            if name in List_tmp:
                self.userConfig[str(_List) + '_tmp'].remove(name)
            else:
                self.userConfig[str(_List) + '_tmp'].append(name)

    def add_cateManualLiveExtra(self, action, name, id):
        _Extra = self.userConfig.get('cateManualLiveExtra', [])
        if not _Extra:
            _Extra = self.userConfig['cateManualLiveExtra'] = []
        if action == 'clear':
            for _ext in _Extra:
                _ext['v'] = _ext['v'].replace('@@@', '_')
                if _ext in self.userConfig.get('cateManualLive', []):
                    self.userConfig['cateManualLive'].remove(_ext)
                if _ext in self.userConfig.get('cateManualLive_tmp', []):
                    self.userConfig['cateManualLive_tmp'].remove(_ext)
            self.userConfig.pop('cateManualLiveExtra')
        elif id in list(map(lambda x:x['v'], self.userConfig.get('cateManualLiveExtra', []))):
            area_dict = {'n': name, 'v': id}
            self.userConfig['cateManualLiveExtra'].remove(area_dict)
            area_dict['v'] = id.replace('@@@', '_')
            if area_dict in self.userConfig.get('cateManualLive', []):
                self.userConfig['cateManualLive'].remove(area_dict)
            if area_dict in self.userConfig.get('cateManualLive_tmp', []):
                self.userConfig['cateManualLive_tmp'].remove(area_dict)
        else:
            area_dict = {'n': name, 'v': id}
            self.userConfig['cateManualLiveExtra'].append(area_dict)
        self.dump_config()

    vod_qn_id = {
        '127': "8K",
        '126': "杜比视界",
        '125': "HDR",
        '120': "4K",
        '116': "1080P60帧",
        '112': "1080P+",
        '80': "1080P",
        '64': "720P",
    }
    vod_codec_id = {
        '7': 'avc',
        '12': 'hevc',
        '13': 'av1',
    }
    vod_audio_id = {
        '30251': 'Hi-Res无损',
        '30250': '杜比全景声',
        '30280': '192000',
        '30232': '132000',
        '30216': '64000',
    }

    def get_dash_media(self, media, aid, cid, qn):
        qnid = str(media.get('id'))
        codecid = media.get('codecid', '')
        media_codecs = media.get('codecs')
        media_bandwidth = media.get('bandwidth')
        media_startWithSAP = media.get('startWithSap')
        media_mimeType = media.get('mimeType')
        media_SegmentBase_indexRange = media['SegmentBase'].get('indexRange')
        media_SegmentBase_Initialization = media['SegmentBase'].get('Initialization')
        mediaType = media_mimeType.split('/')[0]
        media_typeParams = ''
        if mediaType == 'video':
            media_frameRate = media.get('frameRate')
            media_sar = media.get('sar')
            media_width = media.get('width')
            media_height = media.get('height')
            media_typeParams = f"height='{media_height}' width='{media_width}' frameRate='{media_frameRate}' sar='{media_sar}'"
        elif mediaType == 'audio':
            audioSamplingRate = self.vod_audio_id.get(qnid, '192000')
            media_typeParams = f"numChannels='2' sampleRate='{audioSamplingRate}'"
        media_BaseURL = f'{self.localProxyUrl}{mediaType}&aid={aid}&cid={cid}&qn={qn}'.replace('&', '&amp;')
        qnid += '_' + str(codecid)
        result = f"""
      <Representation id="{qnid}" bandwidth="{media_bandwidth}" codecs="{media_codecs}" mimeType="{media_mimeType}" {media_typeParams} startWithSAP="{media_startWithSAP}">
        <BaseURL>{media_BaseURL}</BaseURL>
        <SegmentBase indexRange="{media_SegmentBase_indexRange}">
          <Initialization range="{media_SegmentBase_Initialization}"/>
        </SegmentBase>
      </Representation>"""
        self.pC_urlDic[f'{aid}_{cid}'][mediaType] = media
        return result

    def get_dash_media_list(self, media_lis, aid, cid, qn):
        if not media_lis:
            return ""
        mediaType = media_lis[0]['mimeType'].split('/')[0]
        if mediaType == 'video':
            preferQn = str(qn)
            preferCodec = str(self.userConfig['vodDefaultCodec'])
        else: # audio
            preferQn = str(self.userConfig['vodDefaultAudio'])
            preferCodec = '0'
        media_available = {}
        for media in media_lis:
            if mediaType == 'audio' and not media_available:
                media_available = media
            if str(media['id']) == preferQn:
                if not media_available or str(media['codecid']) == preferCodec:
                    media_available = media
                    if str(media['codecid']) == preferCodec:
                        break
        result = f"""
    <AdaptationSet>
      <ContentComponent contentType="{mediaType}"/>{self.get_dash_media(media_available, aid, cid, qn)}
    </AdaptationSet>"""
        return result

    def get_dash(self, ja, aid, cid, qn):
        duration = ja.get('duration')
        minBufferTime = ja.get('minBufferTime')
        video_list = self.pool.submit(self.get_dash_media_list, ja.get('video'), aid, cid, qn)
        audio = ja.get('audio', [])
        dolby = ja.get('dolby', {}).get('audio')
        if dolby:
            audio = dolby + audio
        flac = ja.get('flac')
        if type(flac) == dict:
            audio.insert(0, flac.get('audio'))
        audio_list = self.pool.submit(self.get_dash_media_list, audio, aid, cid, qn)
        mpd = f"""<MPD xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="urn:mpeg:dash:schema:mpd:2011" xsi:schemaLocation="urn:mpeg:dash:schema:mpd:2011 DASH-MPD.xsd" type="static" mediaPresentationDuration="PT{duration}S" minBufferTime="PT{minBufferTime}S" profiles="urn:mpeg:dash:profile:isoff-on-demand:2011">
  <Period duration="PT{duration}S" start="PT0S">{video_list.result()}{audio_list.result()}
  </Period>
</MPD>"""
        return mpd

    def miao(self, m):
        m = str(m).partition('.')[2]    #取小数部分
        if len(m)==0:m = '000'          #补齐三位小数
        if len(m)==1:m = m + '00'
        if len(m)==2:m = m + '0'
        return m                           #返回标准三位的毫秒数

    def down_sub(self, url):
        data = self._get_sth(url, 'fake').json()['body']
        srt = ''
        i=1
        for d in data:
            f = round(d['from'],3)      # 开始时间 （round(n，3)四舍五入为三位小数）
            t = round(d['to'],3)        # 结束时间
            c = d['content']            # 字幕内容
            ff = time.strftime("%H:%M:%S",time.gmtime(f)) + ',' + self.miao(f)   # 开始时间，秒数转 时:分:秒 格式，加逗号、毫秒修正为三位
            tt = time.strftime("%H:%M:%S",time.gmtime(t)) + ',' + self.miao(t)   # 结束时间，处理方式同上
            srt += str(i) + '\n' + ff + ' ' + '-->' + ' ' + tt + '\n' + c + '\n\n'     # 格式化为Srt字幕
            i += 1
        return srt

    localProxyUrl = 'http://127.0.0.1:9978/proxy?do=py&siteType=3&siteKey=py_bilibili&type='

    def get_subs(self, aid, cid):
        result = []
        url = f'https://api.bilibili.com/x/player/wbi/v2?aid={aid}&cid={cid}'
        data = self._get_sth(url, 'master').json().get('data')
        if data:
            for sub in data['subtitle'].get('subtitles', []):
                lanDoc = str(sub.get('lan_doc', ''))
                lanUrl = sub.get('subtitle_url')
                if lanUrl.startswith('//'):
                    lanUrl = 'https:' + lanUrl
                lanUrl = quote(lanUrl)
                result.append(
                    {
                        "url": f"{self.localProxyUrl}subtitle&url={lanUrl}",
                        "name": lanDoc,
                        "format": "application/x-subrip"
                    }
                )
            if result:
                result.insert(0,
                    {
                        "url": "",
                        "name": " ",
                        "format": "application/x-subrip"
                    }
                )
        played_time = 0
        if int(data.get('last_play_cid', 0)) == int(cid):
            played_time = int(data.get('last_play_time'))
            if played_time > 0:
                played_time = int(played_time / 1000)
        graph_version = data.get('interaction', {}).get('graph_version', '')
        return result, played_time, graph_version

    pC_urlDic = {}
    def _get_playerContent(self, result, aid, cid, epid):
        self.pC_urlDic[f'{aid}_{cid}'] = urlDic = {**self.pC_urlDic.get(f'{aid}_{cid}', {}), 'epid': epid}
        vodDefaultQn = self.userConfig['vodDefaultQn']
        if epid:
            url = 'https://api.bilibili.com/pgc/player/web/v2/playurl?aid={}&cid={}&qn={}&fnval=4048&fnver=0&fourk=1&from_client=BROWSER'.format(aid, cid, vodDefaultQn)
        else:
            arg={'avid':aid, 'cid': cid, 'qn':vodDefaultQn, 'fnval': 4048, 'fnver': 0, 'fourk': 1, 'from_client': 'BROWSER', 'gaia_source': 'pre-load', 'isGaiaAvoided': 'true'}
            if not self.session_vip.cookies:
                arg['try_look'] = 1
            query = self.encrypt_wbi(**arg)[0]
            url = f'https://api.bilibili.com/x/player/wbi/playurl?{query}'
        jRoot = self._get_sth(url, 'vip').json()
        ssid = ''
        if jRoot['code'] == 0:
            if 'data' in jRoot:
                jo = jRoot['data']
            elif 'result' in jRoot:
                jo = jRoot['result']
                if 'video_info' in jo:
                    jr = jo['view_info']['report']
                    ssid = jr['season_id']
                    epid = jr['ep_id']
                    jo = jo['video_info']
            else:
                return result
        else:
            return result
        urlDic['ssid'] = ssid
        urlDic['epid'] = epid
        formats = dict(map(lambda x:(x['quality'], x['new_description']), jo['support_formats']))
        result["url"] = []
        ja = jo.get('dash')
        _param = f'&aid={aid}&cid={cid}&qn='
        if ja:
            urlDic['mpd'] = ja
            result["format"] = 'application/dash+xml'
            for video in ja['video']:
                id = video['id']
                desc = formats[id]
                if not desc in result["url"]:
                    url = f'{self.localProxyUrl}dash{_param}{id}'
                    if id == int(vodDefaultQn):
                        result["url"] = [desc, url] + result["url"]
                    else:
                        result["url"].extend([desc, url])
        elif 'durls' in jo:
            for durl in jo['durls']:
                qn = durl['quality']
                desc = formats[qn]
                url = f'{self.localProxyUrl}durl{_param}{qn}'
                if qn == int(vodDefaultQn):
                    result["url"] = [desc, url] + result["url"]
                else:
                    result["url"].extend([desc, url])
                urlDic[str(qn)] = durl['durl'][0]
        else:
            qn = jo['quality']
            urlDic[str(qn)] = jo['durl'][0]
            result["url"] = f'{self.localProxyUrl}durl{_param}{qn}'
        urlDic['result'] = {**urlDic.get('result', {}), **result}
        return result, ssid, epid

    def _refreshDetail(self, t=0):
        time.sleep(int(t))
        self.fetch('http://127.0.0.1:9978/action?do=refresh&type=detail')

    def playerContent(self, flag, id, vipFlags):
        self.pool.submit(self.stop_heartbeat)
        result = {}
        this_array = ''
        if '@' in id:
            id, this_array = id.split("@")
        array = self.detailContent_args.get(this_array, self.detailContent_args)
        ids = id.split("_")
        if len(ids) < 2:
            return result
        if 'live' == ids[0]:
            return self.live_playerContent(id)
        aid = ids[0]
        cid = ids[1]
        if 'setting' in ids:
            if 'liveFilter' in ids:
                id = ids[2]
                self.add_cateManualLiveExtra(aid, cid, id)
            elif cid in ['cateManual', 'cateManualLive', 'tuijianLis', 'rankingLis']:
                action = ids[2]
                self.set_normal_cateManual(aid, cid, action)
            elif 'login' in ids:
                self.set_cookie(aid, cid)
            elif 'logout' in ids:
                self.unset_cookie(aid)
            else:
                self.set_normal_default(aid, cid)
            return result
        elif 'notplay' in ids:
            self.pool.submit(self.do_notplay, ids)
            return result
        elif 'interaction' in ids:
            array['edgeid'] = aid
            array['cid'] = cid
            self.pool.submit(self._refreshDetail)
            return result
        aid, cid, epid, dur, parse = id.split("_")
        if not cid or not dur:
            cid, dur, epid = self.get_cid(aid, cid)
        result["danmaku"] = 'https://api.bilibili.com/x/v1/dm/list.so?oid=' + str(cid)
        if parse:
            url = 'https://www.bilibili.com/bangumi/play/ep' + str(epid)
            result["url"] = url
            result["flag"] = 'bilibili'
            result["parse"] = '1'
            result['jx'] = '1'
            result["header"] = {"User-Agent": self.header["User-Agent"]}
            return result
        get_sub = self.pool.submit(self.get_subs, aid, cid)
        urlDic = self.pC_urlDic.get(f'{aid}_{cid}')
        if urlDic:
            result, ssid, epid = urlDic['result'], urlDic['ssid'], urlDic['epid']
        else:
            result["parse"] = '0'
            result["contentType"] = ''
            result["header"] = self.header
            result, ssid, epid = self._get_playerContent(result, aid, cid, epid)
        result["subs"], played_time, graph_version = get_sub.result()
        old_gv = array.get('graph_version', '')
        old_aid = array.get('aid')
        if old_aid and aid != old_aid or f'{aid}_{cid}' in array:
            array['aid'] = aid
            self.pool.submit(self._refreshDetail, 1)
        elif graph_version and old_gv != graph_version:
            array['graph_version'] = graph_version
            self.pool.submit(self._refreshDetail)
        else:
            #回传播放记录
            heartbeat = self.pool.submit(self.start_heartbeat, aid, cid, ssid, epid, int(dur), played_time)
            self.task_pool.append(heartbeat)
        return result

    def live_playerContent(self, id):
        api, room_id, qn, format, codec = id.split("_")
        # 回传观看直播记录
        if self.userid and int(self.userConfig['heartbeatInterval']) > 0:
            self.pool.submit(self.post_live_history, room_id)
        url = 'https://api.live.bilibili.com/xlive/web-room/v2/index/getRoomPlayInfo?room_id={0}&protocol=0,1&format={1}&codec={2}&qn={3}&ptype=8&platform=web&dolby=5&panorama=1'.format(room_id, format, codec, qn)
        jo = self._get_sth(url, 'vip').json()
        result = {}
        if jo['code'] == 0:
            try:
                playurl = jo['data']['playurl_info'].get('playurl')
                codec = playurl['stream'][0]['format'][0]['codec'][0]
            except:
                return result
            base_url = str(codec['base_url'])
            host = str(codec['url_info'][0]['host'])
            extra = str(codec['url_info'][0]['extra'])
            playurl = host + base_url + extra
            result["url"] = playurl
            result["contentType"] = ''
            if ".flv" in playurl: result["contentType"] = 'video/x-flv'
        else:
            return result
        result["parse"] = '0'
        result["header"] = {
            "Referer": "https://live.bilibili.com",
            "User-Agent": self.header["User-Agent"]
        }
        return result

    def get_fastesUrl(self, ja, id, mediaType):
        urlList = ja
        if type(ja) == dict:
            self.pC_urlDic[id][mediaType] = urlList = [ja.get('baseUrl', ja.get('url', ''))]
            urlList.extend(ja.get('backup_url', []))
            self.pC_urlDic[id]['deadline'] = int(dict(map(lambda x: x.split('=')[:2], urlList[0].split('?')[1].split('&'))).get('deadline', 0))
        futures = {self.pool.submit(head, url, headers=self.header, timeout=2): url for url in urlList}
        for future in as_completed(futures):
            url = futures[future]
            try:
                resp = future.result()
                if resp.status_code == 200:
                    self.pC_urlDic[id][mediaType] = url
                    return url
            except:
                continue

    def localProxy(self, param):
        _type = param.get('type')
        if _type == 'subtitle':
            content = self.down_sub(param['url'])
            return [200, "application/octet-stream", content]
        aid = param.get('aid')
        cid = param.get('cid')
        qn = param.get('qn')
        urlDic = self.pC_urlDic[f'{aid}_{cid}']
        if _type == 'dash':
            mpd = self.get_dash(urlDic['mpd'], aid, cid, qn)
            return [200, "application/dash+xml", mpd]
        if _type in ['durl', 'video', 'audio']:
            if _type == 'durl':
                _type = qn
            _nowtime = round(time.time())
            _deadline = urlDic.get('deadline')
            if type(urlDic[_type]) == dict or (_deadline - _nowtime) % 10 == 0:
                self.get_fastesUrl(urlDic[_type], f'{aid}_{cid}', _type)
                _deadline = urlDic.get('deadline')
            url = urlDic[_type]
            if type(url) != str or _type != 'audio' and _deadline - _nowtime < 1800:
                self._get_playerContent({}, aid, cid, urlDic['epid'])
                urlDic = self.pC_urlDic[f'{aid}_{cid}']
                if _type == 'video':
                    self.get_dash(urlDic['mpd'], aid, cid, qn)
                url = self.get_fastesUrl(urlDic[_type], f'{aid}_{cid}', _type)
            header = self.header.copy()
            if 'range' in param:
                header['Range'] = param['range']
            r = self.fetch(url, headers=header, stream=True)
            return [206, "application/octet-stream", r.content]
        return [404, "text/plain", ""]

    config = {
        "player": {},
        "filter": {
            "关注": [{"key": "sort", "name": "分类",
                      "value": [{"n": "正在直播", "v": "正在直播"}, {"n": "最常访问", "v": "最常访问"},
                                {"n": "最近关注", "v": "最近关注"}, {"n": "特别关注", "v": "特别关注"},
                                {"n": "悄悄关注", "v": "悄悄关注"}, {"n": "我的粉丝", "v": "我的粉丝"}]}],
            "动态": [{"key": "order", "name": "投稿排序",
                    "value": [{"n": "最新发布", "v": "pubdate"}, {"n": "最多播放", "v": "click"},
                              {"n": "最多收藏", "v": "stow"}, {"n": "最早发布", "v": "oldest"}, {"n": "合集和列表", "v": "series"}]}, ],
            "影视": [{"key": "tid", "name": "分类",
                      "value": [{"n": "番剧", "v": "1"}, {"n": "国创", "v": "4"}, {"n": "电影", "v": "2"},
                              {"n": "电视剧", "v": "5"}, {"n": "纪录片", "v": "3"}, {"n": "综艺", "v": "7"}]},
                    {"key": "order", "name": "排序",
                      "value": [{"n": "热门", "v": "热门"}, {"n": "播放数量", "v": "2"}, {"n": "更新时间", "v": "0"},
                                {"n": "最高评分", "v": "4"}, {"n": "弹幕数量", "v": "1"}, {"n": "追看人数", "v": "3"},
                                {"n": "开播时间", "v": "5"}, {"n": "上映时间", "v": "6"}]},
                    {"key": "season_status", "name": "付费",
                      "value": [{"n": "全部", "v": "-1"}, {"n": "免费", "v": "1"},
                                {"n": "付费", "v": "2%2C6"}, {"n": "大会员", "v": "4%2C6"}]}],
            "收藏": [{"key": "order", "name": "排序",
                      "value": [{"n": "收藏时间", "v": "mtime"}, {"n": "播放量", "v": "view"},
                                {"n": "投稿时间", "v": "pubtime"}]}, ],
            "历史": [{"key": "type", "name": "分类",
                          "value": [{"n": "视频", "v": "archive"}, {"n": "直播", "v": "live"}, {"n": "UP主", "v": "UP主"}, {"n": "稍后再看", "v": "稍后再看"}]}, ],
            "搜索": [{"key": "type", "name": "类型",
                      "value": [{"n": "视频", "v": "video"}, {"n": "番剧", "v": "media_bangumi"}, {"n": "影视", "v": "media_ft"},
                                {"n": "直播", "v": "live"}, {"n": "用户", "v": "bili_user"}]},
                    {"key": "order", "name": "视频排序",
                      "value": [{"n": "综合排序", "v": "totalrank"}, {"n": "最多点击", "v": "click"}, {"n": "最新发布", "v": "pubdate"},
                                {"n": "最多收藏", "v": "stow"}, {"n": "最多弹幕", "v": "dm"}]},
                    {"key": "duration", "name": "视频时长",
                      "value": [{"n": "全部", "v": "0"}, {"n": "60分钟以上", "v": "4"}, {"n": "30~60分钟", "v": "3"},
                                {"n": "5~30分钟", "v": "2"}, {"n": "5分钟以下", "v": "1"}]}],
        }
    }

    header = {
        'Origin': 'https://www.bilibili.com',
        'Referer': 'https://space.bilibili.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0'
    }
