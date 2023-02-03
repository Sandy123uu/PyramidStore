# coding=utf-8
# !/usr/bin/python
import sys, os, json
from base.spider import Spider
from requests import session, utils, get as requests_get
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import random
from urllib.parse import quote, urlencode

sys.path.append('..')
dirname, filename = os.path.split(os.path.abspath(__file__))
sys.path.append(dirname)

class Spider(Spider):
    #默认设置
    defaultConfig = {
        'currentVersion': "20230202_2",
        #【建议通过扫码确认】设置Cookie，在双引号内填写
        'raw_cookie_line': "",
        #如果主cookie没有vip，可以设置第二cookie，仅用于播放会员番剧，所有的操作、记录还是在主cookie，不会同步到第二cookie
        'raw_cookie_vip': "buvid3=908FE240-2A26-34DB-F165-D3C47593AE2C40797infoc; CURRENT_FNVAL=4048; _uuid=BFB910625-E3D4-5578-11C1-476DEC54DCE342607infoc; buvid4=11AAA057-239C-44FF-61D6-4871335E59B145245-022060422-ydfccpBcvbRqXU//8J/8mg==; CURRENT_BLACKGAP=0; blackside_state=0; fingerprint=5b65597340b791eafe510854e1aee762; buvid_fp_plain=undefined; buvid_fp=5b65597340b791eafe510854e1aee762; hit-dyn-v2=1; innersign=0; b_nut=100; i-wanna-go-back=-1; b_lsid=109B74D10D_1854FE03A1B; SESSDATA=f9a14e23,1687634471,081c9*c2; bili_jct=bf318e14a5134987277d0a03c6deeae0; DedeUserID=26057693; DedeUserID__ckMd5=e6e06406457f3048; sid=oblopuch; PVID=1; b_ut=5",
        #主页默认显示20图
        'maxHomeVideoContent': '20',
        #收藏标签默认显示追番1，追剧2，默认收藏夹0
        'favMode': '0',
        #部分视频列表分页，限制每次加载数量
        'page_size': 10,
        #上传播放进度间隔时间，单位秒，b站默认间隔15，0则不上传播放历史
        'heartbeatInterval': '15',
        #视频默认画质ID
        'vodDefaultQn': '80',
        #视频默认解码ID
        'vodDefaultCodec': '7',
        #音频默认码率ID
        'vodDefaultAudio': '30280',
        #获取视频热门评论
        'show_vod_hot_reply': True,
        #从正片中拆分出番剧的预告
        'hide_bangumi_preview': True,
        #登陆会员账号后，影视播放页不显示会员专享的标签，更简洁
        'hide_bangumi_vip_badge': False,
        #影视播放页是否显示花絮、PV、番外等非正片内容，无正片时不受此设定影响
        'show_bangumi_pv': True,
        #番剧（热门）列表使用横图
        'bangumi_horizontal_cover': True,
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
            "频道",
            "收藏",
            "关注",
            "历史",
            "搜索",
        ],
        #自定义推荐标签的筛选
        'tuijianList': [
            "热门",
            "排行榜",
            "每周必看",
            "入站必刷",
            "番剧时间表",
            "国创时间表",
            "动画",
            "音乐",
            "舞蹈",
            "游戏",
            "鬼畜",
            "知识",
            "科技",
            "运动",
            "生活",
            "美食",
            "动物",
            "汽车",
            "时尚",
            "娱乐",
            "影视",
            "原创",
            "新人",
        ],
    }

    #在动态标签的筛选中固定显示他，n为用户名或任意都可以，v必须为准确的UID
    focus_on_up_list = [
        #{"n":"培根悖论唠唠嗑", "v":"386869863"},
    ]
    
    #在搜索标签的筛选中固定显示搜索词
    focus_on_search_key = [
        '哈利波特',
        '演唱会',
        'MV',
        '假窗'
    ]

    def getName(self):
        return "哔哩哔哩"

    def load_config(self):
        try:
            with open(f"{dirname}/config.json",encoding="utf-8") as f:
                self.userConfig = json.load(f)
            old_config = {
                'vod_default_qn': 'vodDefaultQn',
                'vod_default_codec': 'vodDefaultCodec',
                'vod_default_audio': 'vodDefaultAudio',
            }
            for old, new in old_config.items():
                if old in self.userConfig:
                    self.userConfig[new] = str(self.userConfig[old])
            old_config = {
                'master': 'cookie_dic',
                'vip': 'cookie_vip_dic',
                'fake': 'cookie_fake_dic',
            }
            for _type, old in old_config.items():
                old = self.userConfig.get(old)
                if old:
                    if not self.userConfig.get('users'):
                        self.userConfig['users'] = {}
                    self.userConfig['users'][_type] = {'cookies_dic': old}
            users = self.userConfig.get('users', {})
            if users.get('master') and users['master'].get('cookies_dic'):
                self.session_master.cookies = utils.cookiejar_from_dict(users['master']['cookies_dic'])
            if users.get('fake') and users['fake'].get('cookies_dic'):
                self.session_fake.cookies = utils.cookiejar_from_dict(users['fake']['cookies_dic'])
        except:
            self.userConfig = {}
        self.userConfig = {**self.defaultConfig, **self.userConfig}

    dump_config_lock = threading.Lock()
    
    def dump_config(self):
        needSaveConfig = ['users', 'channel_list', 'cateLive', 'cateManualLive', 'cateManualLiveExtra']
        userConfig_new = {}
        for key, value in self.userConfig.items():
            dafalutValue = self.defaultConfig.get(key)
            if dafalutValue != None and value != dafalutValue or key in needSaveConfig:
                userConfig_new[key] = value
        self.dump_config_lock.acquire()
        with open(f"{dirname}/config.json", 'w', encoding="utf-8") as f:
            data = json.dumps(userConfig_new, indent=1, ensure_ascii=False)
            f.write(data)
        self.dump_config_lock.release()

    # 主页
    def homeContent(self, filter):
        with ThreadPoolExecutor(max_workers=3) as pool:
            pool.submit(self.add_live_filter)
            pool.submit(self.add_channel_filter)
            pool.submit(self.add_search_key)
            pool.submit(self.get_tuijian_filter)
            pool.submit(self.add_focus_on_up_filter)
            pool.submit(self.add_fav_filter)
            pool.submit(self.homeVideoContent)
        result = {}
        classes = []
        needLogin = ['动态', '收藏', '关注', '历史']
        cateManual = self.userConfig['cateManual']
        if not self.userid and not 'UP' in cateManual or not '动态' in cateManual and not 'UP' in cateManual:
            cateManual += ['UP']
        for k in cateManual:
            if k in needLogin and not self.userid:
                continue
            classes.append({
                'type_name': k,
                'type_id': k
            })
        self.add_focus_on_up_filter_event.wait()
        if 'UP' in cateManual:
            self.config["filter"].update({'UP': self.config["filter"].pop('动态')})
        result['class'] = classes
        if filter:
            result['filters'] = self.config['filter']
        t = threading.Thread(target=self.dump_config)
        t.start()
        t = threading.Thread(target=self._checkUpdate, args=('0',))
        t.start()
        return result

    # 用户cookies
    cookies = cookies_vip = userid = csrf = ''
    session_master = session()
    session_vip = session()
    session_fake = session()
    con = threading.Condition()
    getCookie_event = threading.Event()

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
        with self.con:
            if len(user) > 1:
                users[_type] = user
            if _type == 'master':
                self.getCookie_event.set()

    getFakeCookie_event = threading.Event()

    def getFakeCookie(self, fromSearch=None):
        if self.session_fake.cookies:
            self.getFakeCookie_event.set()
        rsp = self.fetch('https://www.bilibili.com', headers=self.header)
        self.session_fake.cookies = rsp.cookies
        self.getFakeCookie_event.set()
        with self.con:
            users = self.userConfig.get('users', {})
            users['fake'] = {'cookies_dic': dict(rsp.cookies)}
        if not fromSearch:
            self.getCookie_event.wait()
            if not self.session_master.cookies:
                self.session_master.cookies = rsp.cookies
        
    def get_fav_list_dict(self, fav):
        fav_dict = {
            'n': fav['title'].replace("<em class=\"keyword\">", "").replace("</em>", "").replace("&quot;",'"').strip(),
            'v': fav['id']}
        return fav_dict

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
            rsp = self._get_sth(url)
            jo = json.loads(rsp.text)
            if jo['code'] == 0 and jo.get('data'):
                fav = jo['data'].get('list')
                fav_list = list(map(self.get_fav_list_dict, fav))
        fav_top = [{"n": "追番", "v": "1"},{"n": "追剧", "v": "2"}]
        fav_config = self.config["filter"].get('收藏')
        if fav_config:
            fav_config.insert(0, {
                "key": "mlid",
                "name": "分区",
                "value": fav_top + fav_list,
            })
        self.userConfig["fav_list"] = fav_list.copy()
        self.add_fav_filter_event.set()

    def get_channel_list_dict(self, channel):
        channel_dict = {
            'n': channel['name'].replace("<em class=\"keyword\">", "").replace("</em>", "").replace("&quot;",'"').strip(),
            'v': channel['id']}
        return channel_dict

    def get_channel_list(self):
        url = 'https://api.bilibili.com/x/web-interface/web/channel/category/channel/list?id=100&offset=0&page_size=15'
        rsp = self._get_sth(url, 'fake')
        jo = json.loads(rsp.text)
        channel_list = []
        if jo['code'] == 0:
            channel = jo['data'].get('channels')
            self.userConfig['channel_list'] = list(map(self.get_channel_list_dict, channel))
            t = threading.Thread(target=self.dump_config)
            t.start()
        return self.userConfig['channel_list']

    add_channel_filter_event = threading.Event()

    def add_channel_filter(self):
        channel_list = self.userConfig.get('channel_list', '')
        if not channel_list:
            channel_list = self.get_channel_list()
        else:
            t = threading.Thread(target=self.get_channel_list)
            t.start()
        channel_config = self.config["filter"].get('频道')
        if channel_config:
            channel_config.insert(0, {
                "key": "cid",
                "name": "分区",
                "value": channel_list,
            })
        self.add_channel_filter_event.set()

    add_focus_on_up_filter_event = threading.Event()

    def add_focus_on_up_filter(self):
        first_list = [{"n": "上个视频的UP主", "v": "上个视频的UP主"}]
        up_list = []
        if not self.session_master.cookies:
            self.getCookie_event.wait()
        if self.session_master.cookies:
            url = 'https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/all?timezone_offset=-480&type=video&page=1'
            rsp = self._get_sth(url)
            jo = json.loads(rsp.text)
            if jo['code'] == 0 and jo.get('data'):
                up = jo['data'].get('items', [])
                up_list = list(map(lambda x: {'n': x['modules']["module_author"]['name'], 'v': str(x['modules']["module_author"]['mid'])}, up))
        if len(self.focus_on_up_list) > 0:
            focus_on_up_list_mid = list(map(lambda x: x['v'], self.focus_on_up_list))
            for item in up_list:
                if item['v'] in focus_on_up_list_mid:
                    up_list.remove(item)
            up_list.extend(self.focus_on_up_list)
        last_list = [{"n": "登录与设置", "v": "登录"}]
        up_list = first_list + up_list + last_list
        dynamic_config = self.config["filter"].get('动态')
        if dynamic_config:
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
        rsp = self._get_sth(url, 'fake')
        jo = json.loads(rsp.text)
        cateLive = {}
        if jo['code'] == 0:
            parent = jo['data']['data']
            self.userConfig['cateLive'] = dict(map(self.get_live_parent_area_list, parent))
            t = threading.Thread(target=self.dump_config)
            t.start()
        return self.userConfig['cateLive']

    set_default_cateManualLive_event = threading.Event()

    def set_default_cateManualLive(self):
        cateManualLive = [{'n': '推荐', 'v': '推荐'},]
        for name in self.userConfig['cateLive']:
            area_dict = {'n': name, 'v': self.userConfig['cateLive'][name]['id']}
            cateManualLive.append(area_dict)
        self.defaultConfig['cateManualLive'] = cateManualLive
        self.set_default_cateManualLive_event.set()

    add_live_filter_event = threading.Event()

    def add_live_filter(self):
        cateLive = self.userConfig.get('cateLive', {})
        if cateLive:
            t = threading.Thread(target=self.get_live_list)
            t.start()
        else:
            cateLive = self.get_live_list()
        t = threading.Thread(target=self.set_default_cateManualLive)
        t.start()
        self.config["filter"]['直播'] = []
        #分区栏
        cateManualLive = self.userConfig.get('cateManualLive', [])
        if not cateManualLive:
            self.set_default_cateManualLive_event.wait()
            cateManualLive = self.defaultConfig['cateManualLive']
        if cateManualLive:
            live_area = {'key': 'tid', 'name': '分区', 'value': cateManualLive}
            self.config["filter"]['直播'].append(live_area)
        #显示分区细分
        if int(self.userConfig['showLiveFilterTag']):
            for name in cateLive.values():
                if len(name['value']['value']) == 1:
                    continue
                self.config["filter"]['直播'].append(name['value'])
        self.add_live_filter_event.set()

    def add_search_key(self):
        focus_on_search_key = self.focus_on_search_key
        url = 'https://api.bilibili.com/x/web-interface/wbi/search/square?limit=10&platform=web'
        rsp = self._get_sth(url, 'fake')
        jo = json.loads(rsp.text)
        cateLive = {}
        if jo['code'] == 0:
            trending = jo['data']['trending'].get('list', [])
            focus_on_search_key += list(map(lambda x:x['keyword'], trending))
        keyword = {"key": "keyword", "name": "搜索词","value": []}
        keyword["value"] = list(map(lambda i: {'n': i, 'v': i}, focus_on_search_key))
        self.config["filter"]['搜索'].insert(0, keyword)

    def get_tuijian_filter(self):
        tuijian_filter = {"番剧时间表": "10001", "国创时间表": "10004", "排行榜": "0", "动画": "1", "音乐": "3", "舞蹈": "129", "游戏": "4", "鬼畜": "119", "知识": "36", "科技": "188", "运动": "234", "生活": "160", "美食": "211", "动物": "217", "汽车": "223", "时尚": "155", "娱乐": "5", "影视": "181", "原创": "origin", "新人": "rookie"}
        tf_list = {"key": "tid", "name": "分类", "value": []}
        tuijianList = self.userConfig.get('tuijianList')
        if not tuijianList:
            return
        for t in tuijianList:
            tf = tuijian_filter.get(t)
            if not tf:
                tf = t
            tf_dict = {'n': t, 'v': tf}
            tf_list["value"].append(tf_dict)
        self.config["filter"]['推荐'] = tf_list

    def __init__(self):
        self.load_config()
        t = threading.Thread(target=self.getCookie)
        t.start()
        t = threading.Thread(target=self.getFakeCookie)
        t.start()
        t = threading.Thread(target=self.getCookie, args=('vip',))
        t.start()

    def init(self, extend=""):
        print("============{0}============".format(extend))
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
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

    # 按时间过滤
    def filter_duration(self, vodlist, key):
        if key == '0':
            return vodlist
        else:
            vod_list_new = [i for i in vodlist if
                            self.time_diff1[key][0] <= self.str2sec(str(i["vod_remarks"])) < self.time_diff1[key][1]]
            return vod_list_new

    # 提取番剧id
    def find_bangumi_id(self, url):
        aid = str(url).strip().split(r"/")[-1]
        if not aid:
            aid = str(url).strip().split(r"/")[-2]
        aid = aid.split(r"?")[0]
        return aid

    get_qrcode_show_event = threading.Event()
    def get_qrcode_show(self, url):
        header = {
            'Accept': 'image/png',
            'X-QR-Width': '200',
            'X-QR-Height': '200',
            'X-QR-EC-Level': 'M',
        }
        url = 'http://qrcode.show/' + str(url)
        try:
            rsp = requests_get(url=url, headers=header, timeout=(1, 2))
            with open(f"{dirname}/qrcode_show.png", 'wb') as f:
                f.write(rsp.content)
        except:
            self.get_qrcode_show_event.set()
            return
        self.get_qrcode_show_event.set()
        time.sleep(3)
        os.remove(f"{dirname}/qrcode_show.png")

    get_qrcode_tool_lu_event = threading.Event()
    def get_qrcode_tool_lu(self, id):
        header = {"User-Agent": self.header["User-Agent"]}
        url = 'https://tool.lu/qrcode/basic.html?text=https%3A%2F%2Fpassport.bilibili.com%2Fh5-app%2Fpassport%2Flogin%2Fscan%3Fnavhide%3D1%26qrcode_key%3D' + str(id) + '%26from%3D&front_color=%23000000&background_color=%23ffffff&tolerance=15&size=200&margin=50'
        try:
            rsp = requests_get(url=url, headers=header, timeout=(1, 2))
            with open(f"{dirname}/qrcode.png", 'wb') as f:
                f.write(rsp.content)
        except:
            self.get_qrcode_tool_lu_event.set()
            return
        self.get_qrcode_tool_lu_event.set()
        time.sleep(3)
        os.remove(f"{dirname}/qrcode.png")

    # 登录二维码
    def get_Login_qrcode(self, pg):
        result = {}
        if int(pg) != 1:
            return result
        url = 'https://passport.bilibili.com/x/passport-login/web/qrcode/generate'
        rsp = self._get_sth(url, 'fake')
        jo = json.loads(rsp.text)
        if jo['code'] == 0:
            id = jo['data']['qrcode_key']
            url = jo['data']['url']
            #self.get_qrcode_show_event.clear()
            #t = threading.Thread(target=self.get_qrcode_show, args=(url,))
            #t.start()
            #self.get_qrcode_tool_lu_event.clear()
            #t = threading.Thread(target=self.get_qrcode_tool_lu, args=(id,))
            #t.start()
            page_temp = {
                "vod_id": 'setting_login_' + id,
                "vod_name": '有效期3分钟，确认后点这里',
            }
            page = []
            account = {'master': '主账号', 'vip': '副账号'}
            isLogin = {0: '未登录', 1: '已登录'}
            isVIP = {0: '', 1: '👑'}
            users = self.userConfig.get('users', {})
            for _type, typeName in account.items():
                user = users.get(_type)
                if user:
                    page.append({
                        "vod_id": page_temp['vod_id'],
                        "vod_name": user['uname'],
                        "vod_pic": self.format_img(user['face']),
                        "vod_remarks": isVIP[user['isVIP']] + typeName + ' ' + isLogin[user['isLogin']]
                    })
            page.extend([{
                "vod_id": 'setting_tab&filter',
                "vod_name": '标签与筛选',
                "vod_pic": 'https://www.bilibili.com/favicon.ico'
            },{
                "vod_id": 'setting_liveExtra',
                "vod_name": '查看直播细化标签',
                "vod_pic": 'https://www.bilibili.com/favicon.ico'
            }])
            qrpage = page_temp.copy()
            qrpage['vod_pic'] = 'https://qr-api.nyandev.workers.dev/?text=' + quote(url)
            page.append(qrpage)
            qrpage = page_temp.copy()
            pic_url = {}
            pic_url['qrcode'] = url
            pic_url = urlencode(pic_url)
            qrpage['vod_pic'] = 'http://jm92swf.s1002.xrea.com/?' + str(pic_url)
            #qrpage['vod_pic'] = f"file://{dirname}/qrcode.png"
            page.append(qrpage)
            result['list'] = page
            result['page'] = pg
            result['pagecount'] = 1
            result['limit'] = 1
            result['total'] = 1
            #self.get_qrcode_tool_lu_event.wait()
            #self.get_qrcode_show_event.wait()
        return result

    time_diff1 = {'1': [0, 300],
                  '2': [300, 900], '3': [900, 1800], '4': [1800, 3600],
                  '5': [3600, 99999999999999999999999999999999]
                  }
    time_diff = '0'

    dynamic_offset = ''

    def get_dynamic(self, pg, mid, order):
        if mid == '0':
            result = {}
            if int(pg) == 1:
                self.dynamic_offset = ''
            url = 'https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/all?timezone_offset=-480&type=video&offset=%s&page=%s' % (self.dynamic_offset, pg)
            rsp = self._get_sth(url)
            jo = json.loads(rsp.text)
            if jo['code'] == 0:
                self.dynamic_offset = jo['data'].get('offset')
                videos = []
                vodList = jo['data']['items']
                for vod in vodList:
                    if not vod['visible']:
                        continue
                    up = vod['modules']["module_author"]['name']
                    ivod = vod['modules']['module_dynamic']['major']['archive']
                    aid = str(ivod['aid']).strip()
                    title = ivod['title'].strip().replace("<em class=\"keyword\">", "").replace("</em>", "")
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

    def get_found(self, tid, rid, pg):
        result = {}
        if tid == '推荐':
            url = 'https://api.bilibili.com/x/web-interface/wbi/index/top/feed/rcmd?fresh_type=4&feed_version=V8&fresh_idx={0}&fresh_idx_1h={0}&brush={0}&homepage_ver=1&ps={1}'.format(pg, self.userConfig['page_size'])
            rsp = self._get_sth(url)
        else:
            url = 'https://api.bilibili.com/x/web-interface/ranking/v2?rid={0}&type={1}'.format(rid, tid)
            if tid == '热门':
                url = 'https://api.bilibili.com/x/web-interface/popular?pn={0}&ps={1}'.format(pg, self.userConfig['page_size'])
            elif tid == "入站必刷":
                url = 'https://api.bilibili.com/x/web-interface/popular/precious'
            elif tid == "每周必看":
                url = 'https://api.bilibili.com/x/web-interface/popular/series/list'
                rsp = self._get_sth(url, 'fake')
                jo = json.loads(rsp.text)
                number = jo['data']['list'][0]['number']
                url = 'https://api.bilibili.com/x/web-interface/popular/series/one?number=' + str(number)
            rsp = self._get_sth(url, 'fake')
        jo = json.loads(rsp.text)
        if jo['code'] == 0:
            videos = []
            vodList = jo['data'].get('item')
            if not vodList:
                vodList = jo['data']['list']
            if len(vodList) > self.userConfig['page_size']:
                vodList = self.pagination(vodList, pg)
            for vod in vodList:
                aid = vod.get('aid', '')
                if not aid:
                    aid = vod.get('id', '')
                goto = vod.get('goto', '')
                if not goto or goto and goto == 'av':
                    aid = 'av' + str(aid).strip()
                elif goto == 'ad':
                    continue
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
                        continue
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
                        reason = "  💬" + self.zh(vod['stat']['danmaku'])
                    remark = str(self.second_to_time(vod['duration'])).strip() + "  ▶" + self.zh(vod['stat']['view']) + reason
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

    def get_bangumi(self, tid, pg, order, season_status):
        result = {}
        if order == '追番剧':
            url = 'https://api.bilibili.com/x/space/bangumi/follow/list?type={0}&vmid={1}&pn={2}&ps={3}'.format(tid, self.userid, pg, self.userConfig['page_size'])
            rsp = self._get_sth(url)
        else:
            url = 'https://api.bilibili.com/pgc/season/index/result?type=1&season_type={0}&page={1}&order={2}&season_status={3}&pagesize={4}'.format(tid, pg, order, season_status, self.userConfig['page_size'])
            if order == '热门':
                if tid == '1':
                    url = 'https://api.bilibili.com/pgc/web/rank/list?season_type={0}&day=3'.format(tid)
                else:
                    url = 'https://api.bilibili.com/pgc/season/rank/web/list?season_type={0}&day=3'.format(tid)
            rsp = self._get_sth(url, 'fake')
        jo = json.loads(rsp.text)
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
                if not img or tid == '1' and not self.userConfig['bangumi_horizontal_cover']:
                    if vod.get('first_ep_info') and 'cover' in vod['first_ep_info']:
                        img = vod['first_ep_info']['cover']
                    elif vod.get('first_ep') and 'cover' in vod['first_ep']:
                        img = vod['first_ep']['cover']
                    else:
                        img = vod['cover'].strip()
                remark = vod.get('index_show')
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
        rsp = self._get_sth(url, 'fake')
        content = rsp.text
        jo = json.loads(content)
        if jo['code'] == 0:
            videos1 = []
            vodList = jo['result']['latest']
            for vod in vodList:
                aid = str(vod['season_id']).strip()
                title = vod['title'].strip()
                img = vod['cover'].strip()
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
                        img = str(vod['cover']).strip()
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
            url = 'https://api.live.bilibili.com/xlive/web-interface/v1/webMain/getList?platform=web&page=%s' % pg
            rsp = self._get_sth(url)
        else:
            url = 'https://api.live.bilibili.com/xlive/web-interface/v1/second/getList?platform=web&parent_area_id=%s&area_id=%s&sort_type=online&page=%s' % (parent_area_id, area_id, pg)
            if parent_area_id == '热门':
                url = 'https://api.live.bilibili.com/room/v1/room/get_user_recommend?page=%s&page_size=%s' % (pg, self.userConfig['page_size'])
            rsp = self._get_sth(url, 'fake')
        jo = json.loads(rsp.text)
        if jo['code'] == 0:
            videos = []
            vodList = jo['data']
            if 'recommend_room_list' in vodList:
                vodList = vodList['recommend_room_list']
            elif 'list' in vodList:
                vodList = vodList['list']
            for vod in vodList:
                aid = str(vod['roomid']).strip()
                title = vod['title'].replace("<em class=\"keyword\">", "").replace("</em>", "").replace("&quot;", '"')
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

    get_up_videos_event = threading.Event()
    get_up_videos_result = {}
    
    def get_up_videos(self, mid, pg, order):
        result = {}
        if not mid.isdigit():
            if int(pg) == 1:
                self.get_up_videos_mid = mid = self.detailContent_args.get('mid', '')
                if not mid in self.get_up_videos_result:
                    self.get_up_videos_result.clear()
                    self.get_up_videos_result[mid] = []
            else:
                mid = self.get_up_videos_mid
        if int(pg) == 1:
            self.get_up_info_event.clear()
            t = threading.Thread(target=self.get_up_info, kwargs={'mid': mid, })
            t.start()
        Space = order2 = ''
        if order == 'oldest':
            order2 = order
            order = 'pubdate'
        elif order == 'quicksearch':
            Space = '投稿: '
        tmp_pg = pg
        if order2:
            self.get_up_info_event.wait()
            tmp_pg = self.up_info[mid]['vod_pc'] - int(pg) + 1
        url = 'https://api.bilibili.com/x/space/arc/search?mid={0}&pn={1}&ps={2}&order={3}'.format(mid, tmp_pg, self.userConfig['page_size'], order)
        rsp = self._get_sth(url, 'fake')
        content = rsp.text
        jo = json.loads(content)
        videos = []
        if jo['code'] == 0:
            vodList = jo['data']['list']['vlist']
            for vod in vodList:
                aid = str(vod['aid']).strip()
                title = vod['title'].strip().replace("<em class=\"keyword\">", "").replace("</em>", "")
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
                vodname = self.up_info[mid]['name'] + "  个人主页"
                if Space:
                    vodname = 'UP: ' + self.up_info[mid]['name']
                gotoUPHome={
                    "vod_id": 'up' + str(mid),
                    "vod_name": vodname,
                    "vod_pic": self.format_img(self.up_info[mid]['face']),
                    "vod_remarks": self.up_info[mid]['following'] + '  👥' + self.up_info[mid]['fans'] + '  🎬' + str(self.up_info[mid]['vod_count'])
                }
                videos.insert(0, gotoUPHome)
            if Space:
                self.get_up_videos_result[mid] = videos
            result['list'] = videos
            result['page'] = pg
            result['pagecount'] = 99
            result['limit'] = 99
            result['total'] = 999999
        self.get_up_videos_event.set()
        return result

    history_view_at = 0
    
    def get_history(self, type, pg):
        result = {}
        if int(pg) == 1:
            self.history_view_at = 0
        url = 'https://api.bilibili.com/x/web-interface/history/cursor?ps={0}&view_at={1}&type={2}'.format(self.userConfig['page_size'], self.history_view_at, type)
        if type == '稍后再看':
            url = 'https://api.bilibili.com/x/v2/history/toview'
        rsp = self._get_sth(url)
        jo = json.loads(rsp.text)
        if jo['code'] == 0:
            videos = []
            vodList = jo['data']['list']
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
                title = vod['title'].replace("<em class=\"keyword\">", "").replace("</em>", "").replace("&quot;", '"')
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
        rsp = self._get_sth(url)
        content = rsp.text
        jo = json.loads(content)
        if jo['code'] == 0:
            videos = []
            vodList = jo['data']['medias']
            for vod in vodList:
                # 只展示类型为 视频的条目
                # 过滤去掉收藏中的 已失效视频;如果不喜欢可以去掉这个 if条件
                if vod.get('type') in [2] and vod.get('title') != '已失效视频':
                    aid = str(vod['id']).strip()
                    title = vod['title'].replace("<em class=\"keyword\">", "").replace("</em>", "").replace("&quot;",
                                                                                                            '"')
                    img = vod['cover'].strip()
                    remark = str(self.second_to_time(vod['duration'])).strip() + "  ▶" + self.zh(vod['cnt_info']['play']) + "　💬" + self.zh(vod['cnt_info']['danmaku'])
                    videos.append({
                        "vod_id": 'av' + aid + '_mlid' + str(mlid),
                        "vod_name": title,
                        "vod_pic": self.format_img(img),
                        "vod_remarks": remark
                    })
            # videos=self.filter_duration(videos, duration_diff)
            result['list'] = videos
            result['page'] = pg
            result['pagecount'] = 9999
            result['limit'] = 99
            result['total'] = 999999
        return result

    get_up_info_event = threading.Event()
    up_info = {}
    
    def get_up_info(self, mid, **kwargs):
        if mid in self.up_info:
            self.get_up_info_event.set()
        data = kwargs.get('data')
        if not data:
            url = "https://api.bilibili.com/x/web-interface/card?mid={0}".format(mid)
            rsp = self._get_sth(url)
            jRoot = json.loads(rsp.text)
            if jRoot['code'] == 0:
                data = jRoot['data']
            else:
                self.get_up_info_event.set()
                return
        jo = data['card']
        info = {}
        info['following'] = '未关注'
        if data['following']:
            info['following'] = '已关注'
        info['name'] = jo['name'].replace("<em class=\"keyword\">", "").replace("</em>", "")
        info['face'] = jo['face']
        info['fans'] = self.zh(jo['fans'])
        info['like_num'] = self.zh(data['like_num'])
        info['vod_count'] = str(data['archive_count']).strip()
        info['desc'] = jo['Official']['desc'] + "　" + jo['Official']['title']
        pc = divmod(int(info['vod_count']), self.userConfig['page_size'])
        info['vod_pc'] =pc[0]
        if pc[1] != 0:
            info['vod_pc'] += 1
        self.up_info[mid] = info
        self.get_up_info_event.set()

    get_vod_relation_event = threading.Event()
    
    def get_vod_relation(self, id, relation):
        if id.isdigit():
            urlarg = 'aid=' + str(id)
        elif '=' in id:
            urlarg = id
        else:
            urlarg = 'bvid=' + id
        url = 'https://api.bilibili.com/x/web-interface/archive/relation?' + urlarg
        rsp = self._get_sth(url)
        jo = json.loads(rsp.text)
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
        self.get_vod_relation_event.set()

    def get_channel(self, pg, cid, order):
        result = {}
        if str(pg) == '1':
            self.channel_offset = ''
        if order == "featured":
            url = 'https://api.bilibili.com/x/web-interface/web/channel/featured/list?channel_id={0}&filter_type=0&offset={1}&page_size={2}'.format(cid, self.channel_offset, self.userConfig['page_size'])
        else:
            url = 'https://api.bilibili.com/x/web-interface/web/channel/multiple/list?channel_id={0}&sort_type={1}&offset={2}&page_size={3}'.format(cid, order, self.channel_offset, self.userConfig['page_size'])
        rsp = self._get_sth(url, 'fake')
        jo = json.loads(rsp.text)
        if jo.get('code') == 0:
            self.channel_offset = jo['data'].get('offset')
            videos = []
            vodList = jo['data']['list']
            if pg == '1' and 'items' in vodList[0]:
                vodList_rank = vodList[0]['items']
                del (vodList[0])
                vodList = vodList_rank + vodList
            for vod in vodList:
                if 'uri' in vod and 'bangumi' in vod['uri']:
                    aid = self.find_bangumi_id(vod['uri'])
                else:
                    aid = 'av' + str(vod['id']).strip()
                title = vod['name'].replace("<em class=\"keyword\">", "").replace("</em>", "").replace("&quot;", '"')
                img = vod['cover'].strip()
                remark = "▶" + str(vod['view_count'])
                duration = vod.get('duration', '')
                if duration:
                    remark = str(self.second_to_time(self.str2sec(duration))).strip() + '  ' + remark
                danmaku = vod.get('danmaku', '')
                like_count = vod.get('like_count', '')
                follow_count = vod.get('follow_count', '')
                if danmaku:
                    remark += "  💬" + self.zh(danmaku)
                elif like_count:
                    remark += "  👍" + str(like_count)
                elif follow_count:
                    remark += "  ❤" + str(follow_count)
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
        rsp = self._get_sth(url)
        jo = json.loads(rsp.text)
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
                title = f['title'].replace("<em class=\"keyword\">", "").replace("</em>", "").replace("&quot;", '"')
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

    homeVideoContent_result = {}
    
    def homeVideoContent(self):
        if self.homeVideoContent_result == {}:
            videos = self.get_found(rid='0', tid='all', pg=1)['list'][0:int(self.userConfig['maxHomeVideoContent'])]
            self.homeVideoContent_result['list'] = videos
        return self.homeVideoContent_result

    def categoryContent(self, tid, pg, filter, extend):
        t = threading.Thread(target=self.stop_heartbeat)
        t.start()
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
        elif tid == '频道':
            order = 'hot'
            cid = random.choice(self.userConfig['channel_list'])
            cid = cid['v']
            if 'order' in extend:
                order = extend['order']
            if 'cid' in extend:
                cid = extend['cid']
            return self.get_channel(pg=pg, cid=cid, order=order)
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
        elif tid == "UP":
            mid = self.detailContent_args.get('mid', '')
            if 'mid' in extend:
                mid = extend['mid']
            if not mid or mid == '登录':
                return self.get_Login_qrcode(pg)
            up_config = self.config["filter"].get('UP')
            if not mid and up_config:
                for i in up_config:
                    if i['key'] == 'mid':
                        if len(i['value']) > 1:
                            mid = i['value'][1]['v']
                        break
            order = 'pubdate'
            if 'order' in extend:
                order = extend['order']
            return self.get_up_videos(mid=mid, pg=pg, order=order)
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

    search_content_dict = {}

    def get_search_content(self, key, pg, duration_diff, order, type, ps):
        url = 'https://api.bilibili.com/x/web-interface/search/type?keyword={0}&page={1}&duration={2}&order={3}&search_type={4}&page_size={5}'.format(
            key, pg, duration_diff, order, type, ps)
        rsp = self._get_sth(url, 'fake')
        content = rsp.text
        jo = json.loads(content)
        result = {}
        if jo.get('code') == 0 and 'result' in jo['data']:
            videos = []
            vodList = jo['data'].get('result')
            if vodList and type == 'live':
                vodList = vodList.get('live_room')
            if not vodList:
                with self.con:
                    self.search_content_dict[type] = []
                    self.con.notifyAll()
                return result
            for vod in vodList:
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
                    aid = str(vod['season_id']).strip()
                    if self.detailContent_args:
                        seasons = self.detailContent_args.get('seasons')
                        if seasons:
                            bangumi_seasons_id = []
                            for ss in self.detailContent_args['seasons']:
                                bangumi_seasons_id.append(ss['vod_id'])
                            if aid + 'ss' in bangumi_seasons_id:
                                continue
                    aid = 'ss' + aid
                    img = vod['cover'].strip()
                    remark = str(vod['index_show']).strip().replace('更新至', '🆕')
                else:
                    aid = 'av' + str(vod['aid']).strip()
                    img = vod['pic'].strip()
                    remark = str(self.second_to_time(self.str2sec(vod['duration']))).strip() + "  ▶" + self.zh(vod['play']) + "  💬" + self.zh(vod['danmaku'])
                if not title:
                    title = vod['title'].replace("<em class=\"keyword\">", "").replace("</em>", "").replace("&quot;",
                                                                                                        '"').replace('&amp;', '&')
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
        with self.con:
            self.search_content_dict[type] = result.get('list', [])
            self.con.notifyAll()
        return result

    def cleanSpace(self, str):
        return str.replace('\n', '').replace('\t', '').replace('\r', '').replace(' ', '')

    def get_normal_episodes(self, episode):
        ssid = epid = ''
        aid = episode.get('aid', '')
        if not aid:
            aid = self.detailContent_args['aid']
        cid = episode.get('cid', '')
        ep_title = episode.get('title', '')
        if not ep_title:
            ep_title = episode.get('part', '')
        duration = episode.get('duration', '')
        if not duration:
            page = episode.get('page', '')
            if page:
                duration = page['duration']
        badge = long_title = ''
        vod_from = self.detailContent_args.get('from', '')
        if vod_from == 'bangumi':
            epid = episode.get('id', '')
            if epid:
                epid = '_ep' + str(epid)
            ssid = '_ss' + self.detailContent_args['ssid']
            if duration and str(duration).endswith('000'):
                duration = int(duration / 1000)
            if ep_title.isdigit():
                ep_title = '第' + ep_title + self.detailContent_args['title_type']
            badge = episode.get('badge', '')
            if self.session_vip.cookies and self.userConfig['hide_bangumi_vip_badge']:
                badge = badge.replace('会员', '')
            if badge:
                badge = '【' + badge + '】'
            long_title = episode.get('long_title', '')
            if not badge and long_title:
                long_title = ' ' + long_title
        title = ep_title + badge + long_title
        title = title.replace("#", "﹟").replace("$", "﹩")
        if duration:
            duration = '_dur' + str(duration)
        url = '{0}${1}_{2}{3}{4}{5}'.format(title, aid, cid, ssid, epid, duration)
        fromep = self.detailContent_args.get('fromep', '')
        if fromep and fromep == epid.replace('_', ''):
            self.detailContent_args['fromep'] = url
            replyList = self.detailContent_args.get('Reply')
            #获取热门评论
            if self.userConfig['show_vod_hot_reply'] and replyList == None:
                self.detailContent_args['Reply'] = ''
                self.get_vod_hot_reply_event.clear()
                t = threading.Thread(target=self.get_vod_hot_reply, args=(aid, ))
                t.start()
        return url

    get_ugc_season_event = threading.Event()

    def get_ugc_season(self, sections):
        sections_len = len(sections)
        seasonPt = []
        seasonPu = []
        for section in sections:
            if sections_len > 1:
                sec_title = self.detailContent_args['season_title'] + ' ' + section['title']
            else:
                sec_title = self.detailContent_args['season_title']
            sec_title = sec_title.replace("#", "﹟").replace("$", "﹩")
            episodes = section['episodes']
            playUrl = '#'.join(list(map(self.get_normal_episodes, episodes)))
            seasonPt.append(sec_title)
            seasonPu.append(playUrl)
        self.detailContent_args['seasonPt'] = seasonPt
        self.detailContent_args['seasonPu'] = seasonPu
        self.get_ugc_season_event.set()

    get_vod_hot_reply_event = threading.Event()

    def get_vod_hot_reply(self, oid):
        url = 'http://api.bilibili.com/x/v2/reply/main?type=1&ps=30&oid=' + str(oid)
        rsp = self._get_sth(url, 'fake')
        jRoot = json.loads(rsp.text)
        if jRoot['code'] == 0:
            replies = jRoot['data'].get('replies')
            top_replies = jRoot['data'].get('top_replies')
            if replies and top_replies:
                replies = top_replies + replies
            if replies:
                up_mid = jRoot['data']['upper']['mid']
                ReplyList = []
                Reply_jump = []
                for r in replies:
                    rpid = r['rpid']
                    sex = r['member']['sex']
                    if sex and sex == '女':
                        sex = '👧'
                    else:
                        sex = '👦'
                    name = sex + r['member']['uname'] + '：'
                    mid = r['mid']
                    if mid == up_mid:
                        name = '🆙' + name
                    like = '👍' + self.zh(r['like'])
                    message = r['content']['message']
                    if '/note-app/' in message:
                        continue
                    content = like + ' ' + name + message
                    content = content.replace("#", "﹟").replace("$", "﹩")
                    content += '$' + str(oid) + '_' + str(rpid) + '_notplay_reply'
                    ReplyList.append(content)
                    jump_url = r['content'].get('jump_url',{})
                    for key, value in jump_url.items():
                        if not value.get('app_url_schema') and not value.get('pc_url'):
                            if key.startswith('https://b23.tv/'):
                                try:
                                    r = requests_get(url=key, headers=self.header, allow_redirects=False)
                                    url = r.headers['Location'].split('/')
                                    url = str(url[4]).split('?')
                                    key = url[0]
                                except:
                                    continue
                            if not key.startswith('BV'):
                                continue
                            title = str(value['title']).replace("#", "﹟").replace("$", "﹩")
                            vod = {'vod_id': key, 'vod_name': '评论：' + title}
                            if vod in Reply_jump:
                                continue
                            Reply_jump.append(vod)
                            title = '打开快搜看：' + str(key) +' ' + title
                            content = title + '$ '
                            ReplyList.append(content)
                self.detailContent_args['Reply'] = '#'.join(ReplyList)
                self.detailContent_args['Reply_jump'] = Reply_jump
        self.get_vod_hot_reply_event.set()

    get_vod_related_event = threading.Event()

    def get_vod_related(self, jo_Related):
        self.detailContent_args['relatedP'] = ['#'.join(list(map(self.get_normal_episodes, jo_Related)))]
        self.get_vod_related_event.set()

    get_vod_pages_event = threading.Event()

    def get_vod_pages(self, pages):
        self.detailContent_args['firstP'] = ['#'.join(list(map(self.get_normal_episodes, pages)))]
        self.get_vod_pages_event.set()

    detailContent_args = {}
    
    def detailContent(self, array):
        t = threading.Thread(target=self.stop_heartbeat)
        t.start()
        aid = array[0]
        if aid.startswith('edgeid'):
            return self.interaction_detailContent(aid)
        self.detailContent_args = {}
        self.get_vod_hot_reply_event.set()
        if aid.startswith('setting'):
            aid = aid.split('_')
            if aid[1] == 'tab&filter':
                return self.setting_tab_filter_detailContent()
            elif aid[1] == 'liveExtra':
                return self.setting_liveExtra_detailContent()
            elif aid[1] == 'login':
                key = aid[2]
                return self.setting_login_detailContent(key)
        if 'up' in aid:
            return self.up_detailContent(array)
        if 'ss' in aid or 'ep' in aid:
            return self.ysContent(array)
        if aid.isdigit():
            return self.live_detailContent(array)
        id = mlid = urlargs = ''
        for i in aid.split('_'):
            if i.startswith('av', 0, 2):
                id = i.replace('av', '', 1)
                urlargs = 'aid=' + str(id)
            elif i.startswith('BV', 0, 2):
                id = i
                urlargs = 'bvid=' + id
            elif i.startswith('mlid', 0, 4):
                mlid = i.replace('mlid', '', 1)
        #获取热门评论
        if self.userConfig['show_vod_hot_reply']:
            self.detailContent_args['Reply'] = ''
            self.get_vod_hot_reply_event.clear()
            t = threading.Thread(target=self.get_vod_hot_reply, args=(id, ))
            t.start()
        self.get_vod_relation_event.clear()
        relation = []
        t = threading.Thread(target=self.get_vod_relation, args=(urlargs, relation, ))
        t.start()
        url = 'https://api.bilibili.com/x/web-interface/view/detail?' + urlargs
        rsp = self._get_sth(url, 'fake')
        jRoot = json.loads(rsp.text)
        jo = jRoot['data']['View']
        if 'redirect_url' in jo and 'bangumi' in jo['redirect_url']:
            ep_id = self.find_bangumi_id(jo['redirect_url'])
            new_array = []
            for i in array:
                new_array.append(i)
            new_array[0] = ep_id
            return self.ysContent(new_array)
        self.detailContent_args['mid'] = up_mid = str(jo['owner']['mid'])
        self.detailContent_args['aid'] = aid = jo.get('aid')
        #相关合集
        self.get_ugc_season_event.set()
        ugc_season = jo.get('ugc_season')
        if ugc_season:
            self.get_ugc_season_event.clear()
            self.detailContent_args['season_title'] = ugc_season['title']
            sections = ugc_season['sections']
            t = threading.Thread(target=self.get_ugc_season, args=(sections, ))
            t.start()
        #相关推荐
        self.get_vod_related_event.set()
        jo_Related = jRoot['data'].get('Related')
        if jo_Related:
            self.get_vod_related_event.clear()
            t = threading.Thread(target=self.get_vod_related, args=(jo_Related, ))
            t.start()
        #正片
        self.get_vod_pages_event.set()
        pages = jo['pages']
        if pages:
            self.get_vod_pages_event.clear()
            t = threading.Thread(target=self.get_vod_pages, args=(pages, ))
            t.start()
        i = threading.Thread(target=self.get_up_info, kwargs={'mid': up_mid, 'data': jRoot['data'].get('Card'), })
        i.start()
        title = jo['title'].replace("<em class=\"keyword\">", "").replace("</em>", "")
        pic = jo['pic']
        up_name = jo['owner']['name']
        desc = jo['desc'].strip()
        typeName = jo['tname']
        date = time.strftime("%Y%m%d", time.localtime(jo['pubdate']))  # 投稿时间本地年月日表示
        stat = jo['stat']
        # 演员项展示视频状态，包括以下内容：
        status = []
        status.append('▶' + self.zh(stat['view']))
        status.append('💬' + self.zh(stat['danmaku']))
        status.append('👍' + self.zh(stat['like']))
        honor = jo.get('honor_reply')
        if honor:
            status.insert(0, '🏅' + honor['honor'][0]['desc'])
        if not honor or honor and honor['honor'][0]['type'] == 4:
            status.append('💰' + self.zh(stat['coin']))
            status.append('⭐' + self.zh(stat['favorite']))
        remark = str(jo['duration']).strip()
        duration = jo['duration']
        _is_stein_gate = jo['rights'].get('is_stein_gate', 0)
        vod = {
            "vod_id": 'av' + str(aid),
            "vod_name": title, 
            "vod_pic": pic,
            "type_name": typeName,
            "vod_year": date,
            "vod_area": "bilidanmu",
            "vod_remarks": remark,  # 不会显示
         #   'vod_tag': 'folder',  # 不会显示
            "vod_actor": "　".join(status),
            "vod_content": desc
        }
        secondP = []
        if self.userid:
            #做点什么
            follow = '➕关注$1_notplay_follow'
            unfollow = '➖取关$2_notplay_follow'
            like = '👍点赞$1_notplay_like'
            unlike = '👍🏻取消点赞$2_notplay_like'
            coin1 = '👍💰投币$1_notplay_coin'
            coin2 = '👍💰💰投2币$2_notplay_coin'
            triple = '👍💰⭐三连$notplay_triple'
            secondPList = [follow, triple, like, coin1, coin2, unfollow, unlike]
            if mlid:
                favdel = '✩取消收藏${0}_del_notplay_fav'.format(mlid)
                secondPList.append(favdel)
            for fav in self.userConfig.get("fav_list", []):
                folder = fav['n'].replace("#", "﹟").replace("$", "﹩")
                ids = fav['v']
                fav = '⭐{0}${1}_add_notplay_fav'.format(folder, ids)
                secondPList.append(fav)
            defaultQn = int(self.userConfig['vodDefaultQn'])
            if defaultQn > 116:
                secondPList.append('⚠️限高1080$116_notplay_vodTMPQn')
            secondP = ['#'.join(secondPList)]
        AllPt = []
        AllPu = []
        if pages:
            self.get_vod_pages_event.wait()
            AllPt = ['视频分集']
            if _is_stein_gate:
                AllPt = ['互动视频【快搜继续】']
            AllPu = self.detailContent_args['firstP'].copy()
        if secondP:
            AllPt.append('点赞投币收藏')
            AllPu.extend(secondP)
        if jo_Related:
            self.get_vod_related_event.wait()
            AllPt.append('相关推荐')
            AllPu.extend(self.detailContent_args['relatedP'])
        if self.userConfig['show_vod_hot_reply']:
            self.get_vod_hot_reply_event.wait()
            replyList = self.detailContent_args.get('Reply', '')
            if replyList:
                AllPt.append('热门评论')
                AllPu.extend([replyList])
        if ugc_season:
            self.get_ugc_season_event.wait()
            AllPt.extend(self.detailContent_args['seasonPt'])
            AllPu.extend(self.detailContent_args['seasonPu'])
        vod['vod_play_from'] = "$$$".join(AllPt)
        vod['vod_play_url'] = "$$$".join(AllPu)
        #视频关系
        self.get_vod_relation_event.wait()
        self.get_up_info_event.wait()
        vod['vod_director'] = '🆙 ' + up_name + '　👥 ' + self.up_info[up_mid]['fans'] + '　' + '　'.join(relation)
        #互动视频套用
        if _is_stein_gate:
            self.detailContent_args['AllPt'] = AllPt.copy()
            self.detailContent_args['AllPu'] = AllPu.copy()
            self.detailContent_args['vod_list'] = vod.copy()
        result = {
            'list': [
                vod
            ]
        }
        return result

    def interaction_detailContent(self, array=''):
        array = array.split('_')
        cid = edgeid = 0
        for i in array:
            if i.startswith('edgeid'):
                edgeid = i.replace('edgeid', '')
            elif i.startswith('cid'):
                cid = i.replace('cid', '')
        aid = self.detailContent_args.get('aid')
        graph_version = self.detailContent_args.get('graph_version')
        url = 'https://api.bilibili.com/x/stein/edgeinfo_v2?aid={0}&graph_version={1}&edge_id={2}'.format(aid, graph_version, edgeid)
        rsp = self._get_sth(url)
        jo = json.loads(rsp.text)
        data = jo.get('data')
        if data:
            questions = data['edges'].get('questions', [])
            choice_lis = []
            for question in questions:
                q_title = str(question.get('title', ''))
                if q_title:
                    q_title += ' '
                for choice in question.get('choices', []):
                    c_edgeid = str(choice['id'])
                    c_cid = str(choice['cid'])
                    option = str(choice.get('option', ''))
                    choice_lis.append({
                    "vod_id": 'edgeid' + c_edgeid + '_' + 'cid' + c_cid,
                    "vod_name": '互动：' + q_title + option,
                    })
            self.detailContent_args['interaction'] = choice_lis.copy()
            if edgeid:
                AllPt = self.detailContent_args['AllPt'].copy()
                if not choice_lis:
                    AllPt[0] = '互动视频'
                AllPu = self.detailContent_args['AllPu'].copy()
                title = str(data['title']).replace("#", "﹟").replace("$", "﹩")
                url = '{0}${1}_{2}'.format(title, aid, cid)
                AllPu[0] = url
                vod = self.detailContent_args['vod_list'].copy()
                vod['vod_play_from'] = "$$$".join(AllPt)
                vod['vod_play_url'] = "$$$".join(AllPu)
                result = {'list': [vod]}
                return result

    def up_detailContent(self, array):
        self.detailContent_args['mid'] = mid = array[0].replace('up', '')
        self.get_up_info_event.clear()
        i = threading.Thread(target=self.get_up_info, kwargs={'mid': mid, })
        i.start()
        first = '是否关注$ '
        follow = '关注$1_notplay_follow'
        unfollow = '取消关注$2_notplay_follow'
        qqfollow = '悄悄关注$3_notplay_follow'
        spfollow = '特别关注$-10_notplay_special_follow'
        unspfollow = '取消特别关注$0_notplay_special_follow'
        Space = ' $_'
        doWhat = [follow, spfollow, qqfollow, Space, Space, Space, unfollow, unspfollow]
        doWhat = '#'.join(doWhat)
        self.get_up_info_event.wait()
        up_info = self.up_info[mid]
        vod = {
            "vod_id": 'up' + str(mid),
            "vod_name": up_info['name'] + "  个人主页",
            "vod_pic": up_info['face'],
            "vod_remarks": "",  # 不会显示
            "vod_tags": 'mv',  # 不会显示
            "vod_actor": "👥 " + up_info['fans'] + "　🎬 " + up_info['vod_count'] + "　👍 " + up_info['like_num'],
            "vod_director": '🆙 ' + up_info['name'] + "　" + up_info['following'] + '　UID：' +str(mid),
            "vod_content": up_info['desc'],
            'vod_play_from': '关注TA$$$动态标签筛选查看视频投稿'
        }
        vod['vod_play_url'] = doWhat

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
                '6': '6图',
                '8': '8图',
                '10': '10图',
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
        #检查更新
        update_dic = {
            'f': '检查更新',
            'c': 'checkUpdate'
        }
        newVersion = self.userConfig.get('newVersion', '检查失败')
        updateStatus = actionCode = 0
        if newVersion != '检查失败':
            newVersion = '远端：' + str(self.userConfig['newVersion']['ver'])
            actionCode = 1
            updateStatus = self.userConfig['newVersion'].get('status')
        update_dic['d'] = {str(actionCode): newVersion}
        if updateStatus:
            update_dic['d'][' '] = updateStatus
        cate_lis.insert(0, update_dic)
        for cate in cate_lis:
            vod_play_from.append(cate['f'])
            if cate['c'] == 'checkUpdate':
                defaultConfig = self.userConfig['currentVersion']
            else:
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
            {'cateManual': '标签'},
            {'tuijianList': '推荐'},
            {'cateManualLive': '直播'},
        ]
        for cate in cate_lis:
            for _List, _from in cate.items():
                vod_play_from.append(_from)
            List_tmp = self.userConfig.get(str(_List) + '_tmp', [])
            status = ''
            if List_tmp:
                status = '【未保存】'
            else:
                List_tmp = self.userConfig.get(_List, [])
            if not List_tmp:
                List_tmp = self.defaultConfig.get(_List)
            if type(List_tmp[0]) == dict:
                List_tmp = list(map(lambda x:x['n'], List_tmp))
            url = ['当前: ' + ','.join(List_tmp) + '$ ', f"{status}点击这里保存$_{_List}_save_setting", f"点击这里恢复默认并保存$_{_List}_clear_setting"]
            defaultConfig = self.defaultConfig[_List].copy()
            if _List == 'cateManual' and not 'UP' in defaultConfig:
                defaultConfig.append('UP')
            elif _List == 'cateManualLive':
                extra_live_filter = self.userConfig.get('cateManualLiveExtra', [])
                defaultConfig.extend(extra_live_filter.copy())
            for name in defaultConfig:
                value = name
                if type(name) == dict:
                    value = name['n'] + '@@@' + name['v'].replace('_', '@@@')
                    name = name['n']
                url.append(str(name) + '$' + str(value) + f"_{_List}__setting")
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
        if season_id == self.detailContent_args['ssid']:
            self.detailContent_args['s_title'] = season_title
        pic = season['cover']
        remark = season['new_ep']['index_show']
        result = {
            "vod_id": season_id + 'ss',
            "vod_name": '系列：' + season_title,
            "vod_pic": self.format_img(pic),
            "vod_remarks": remark}
        return result

    def add_season_to_search(self, seasons):
        self.detailContent_args['seasons'] = list(map(self.get_all_season, seasons))

    get_bangumi_section_event = threading.Event()

    def get_bangumi_section(self, sections):
        SectionPf = []
        SectionPu = []
        for section in sections:
            sec_title = section['title'].replace("#", "﹟").replace("$", "﹩")
            sec_type = section['type']
            if sec_type in [1, 2] and len(section['episode_ids']) == 0:
                episodes = section['episodes']
                playUrl = '#'.join(list(map(self.get_normal_episodes, episodes)))
                SectionPf.append(sec_title)
                SectionPu.append(playUrl)
        self.detailContent_args['SectionPf'] = SectionPf
        self.detailContent_args['SectionPu'] = SectionPu
        self.get_bangumi_section_event.set()

    get_bangumi_episodes_event = threading.Event()

    def get_bangumi_episodes(self, episodes):
        FirstPu = []
        PreviewPu = []
        ParsePu = []
        for tmpJo in episodes:
            aid = tmpJo['aid']
            cid = tmpJo['cid']
            epid = tmpJo['id']
            duration = tmpJo['duration']
            if str(duration).endswith('000'):
                duration = int(duration / 1000)
            part = tmpJo.get('title', '')
            if part.isdigit():
                part = '第' + part + self.detailContent_args['title_type']
            preview = 0
            badge = tmpJo.get('badge', '')
            parse = ''
            if not self.session_vip.cookies and badge == '会员' and self.userConfig['bangumi_vip_parse'] or badge == '付费' and self.userConfig['bangumi_pay_parse']:
                parse = '_parse'
            if self.session_vip.cookies and self.userConfig['hide_bangumi_vip_badge']:
                badge = badge.replace('会员', '')
            if self.userConfig['hide_bangumi_preview'] and badge == '预告':
                badge = badge.replace('预告', '')
                preview = 1
            if badge:
                badge = '【' + badge + '】'
            long_title = tmpJo.get('long_title', '')
            if not badge and long_title:
                long_title = ' ' + long_title
            title = part + badge + long_title
            title = title.replace("#", "﹟").replace("$", "﹩")
            url = '{0}${1}_{2}_ss{3}_ep{4}_dur{5}'.format(title, aid, cid, self.detailContent_args['ssid'], epid, duration)
            fromep = self.detailContent_args.get('fromep', '')
            if fromep == 'ep' + str(epid):
                self.detailContent_args['fromep'] = url
            replyList = self.detailContent_args.get('Reply')
            if fromep == 'ep' + str(epid) or not fromep and replyList == None:
                self.detailContent_args['Reply'] = ''
                if self.userConfig['show_vod_hot_reply']:
                    self.get_vod_hot_reply_event.clear()
                    t = threading.Thread(target=self.get_vod_hot_reply, args=(aid, ))
                    t.start()
            if preview:
                PreviewPu.append(url)
                continue
            if parse:
                self.detailContent_args['parse'] = 1
                if long_title:
                    long_title = '【解析】' + long_title
                part += long_title
                parseurl = '{0}${1}_{2}_ss{3}_ep{4}_dur{5}{6}'.format(part, aid, cid, self.detailContent_args['ssid'], epid, duration, parse)
                ParsePu.append(parseurl)
                if fromep and fromep == 'ep' + str(epid):
                    self.detailContent_args['fromep'] += '#' + parseurl
            else:
                ParsePu.append(url)
            FirstPu.append(url)
        self.detailContent_args['FirstPu'] = '#'.join(FirstPu)
        if self.detailContent_args.get('parse', ''):
            self.detailContent_args['ParsePu'] = '#'.join(ParsePu)
        if PreviewPu:
            self.detailContent_args['PreviewPu'] = '#'.join(PreviewPu)
        self.get_bangumi_episodes_event.set()

    def ysContent(self, array):
        self.detailContent_args['from'] = 'bangumi'
        aid = array[0]
        if 'ep' in aid:
            self.detailContent_args['fromep'] = aid
            aid = 'ep_id=' + aid.replace('ep', '')
        elif 'ss' in aid:
            aid = 'season_id=' + aid.replace('ss', '')
        url = "https://api.bilibili.com/pgc/view/web/season?{0}".format(aid)
        rsp = self._get_sth(url, 'fake')
        jRoot = json.loads(rsp.text)
        jo = jRoot['result']
        self.detailContent_args['ssid'] = str(jo['season_id'])
        title = jo['title']
        self.detailContent_args['s_title'] = jo['season_title']
        self.detailContent_args['title_type'] = '集'
        if jo['type'] in [1, 4]:
            self.detailContent_args['title_type'] = '话'
        #获取正片
        self.get_bangumi_episodes_event.set()
        episodes = jo['episodes']
        if len(episodes) > 0:
            self.get_bangumi_episodes_event.clear()
            t = threading.Thread(target=self.get_bangumi_episodes, args=(episodes, ))
            t.start()
        section = jo.get('section')
        #获取花絮
        self.get_bangumi_section_event.set()
        if section and not len(jo['episodes']) or section and self.userConfig['show_bangumi_pv']:
            self.get_bangumi_section_event.clear()
            t = threading.Thread(target=self.get_bangumi_section, args=(section, ))
            t.start()
        #添加系列到搜索
        seasons = jo.get('seasons')
        if len(seasons) == 1:
            self.detailContent_args['s_title'] = seasons[0]['season_title']
            self.detailContent_args['seasons'] = []
            seasons = 0
        else:
            t = threading.Thread(target=self.add_season_to_search, args=(seasons, ))
            t.start()
        pic = jo['cover']
        typeName = jo['share_sub_title']
        date = jo['publish']['pub_time'][0:4]
        dec = jo['evaluate']
        remark = jo['new_ep']['desc']
        stat = jo['stat']
        # 演员和导演框展示视频状态，包括以下内容：
        status = "▶" + self.zh(stat['views']) + "　💬" + self.zh(stat['danmakus']) + "　👍" + self.zh(stat['likes']) + "　💰" + self.zh(
            stat['coins']) + "　❤" + self.zh(stat['favorites'])
        if 'rating' in jo:
            status = str(jo['rating']['score']) + '分　' + status
        vod = {
            "vod_id": 'ss' + self.detailContent_args['ssid'],
            "vod_name": title,
            "vod_pic": pic,
            "type_name": typeName,
            "vod_year": date,
            "vod_area": "bilidanmu",
            "vod_remarks": remark,
            "vod_actor": status,
            #"vod_director": score,
            "vod_content": dec
        }
        ZhuiPf = []
        ZhuiPu = []
        if self.userid:
            ZhuiPf = ['追番剧']
            ZhuiPu = ['❤追番剧$add_notplay_zhui#💔取消追番剧$del_notplay_zhui']
        if seasons:
            ZhuiPf.append('更多系列')
            ZhuiPu.append('更多系列在快速搜索中查看$ #')
        self.get_bangumi_episodes_event.wait()
        PreviewPf = []
        PreviewPu = self.detailContent_args.get('PreviewPu', [])
        if PreviewPu:
            PreviewPf.append('预告')
            PreviewPu = [PreviewPu]
        if section:
            self.get_bangumi_section_event.wait()
        FirstPf = []
        FirstPu = self.detailContent_args.get('FirstPu', [])
        if FirstPu:
            FirstPf = [self.detailContent_args['s_title']]
            FirstPu = [FirstPu]
        ParsePf = []
        ParsePu = self.detailContent_args.get('ParsePu', [])
        if ParsePu:
            ParsePf.append(str(self.detailContent_args['s_title']) + '【解析】')
            ParsePu = [ParsePu]
        fromL = ParsePf + FirstPf + PreviewPf + self.detailContent_args.get('SectionPf', [])
        urlL = ParsePu + FirstPu + PreviewPu + self.detailContent_args.get('SectionPu', [])
        fromep = self.detailContent_args.get('fromep', '')
        if '_' in fromep:
            fromL = ['B站'] + fromL
            urlL = [fromep] + urlL
        if self.userConfig['show_vod_hot_reply']:
            self.get_vod_hot_reply_event.wait()
            ReplyPu = self.detailContent_args.get('Reply', '')
            if ReplyPu:
                ZhuiPf.append('热门评论')
                ZhuiPu.append(ReplyPu)
        fromL.insert(1, '$$$'.join(ZhuiPf))
        urlL.insert(1, '$$$'.join(ZhuiPu))
        vod['vod_play_from'] = '$$$'.join(fromL)
        vod['vod_play_url'] = '$$$'.join(urlL)
        result = {
            'list': [
                vod
            ]
        }
        return result

    get_live_api2_playurl_event = threading.Event()

    def get_live_api2_playurl(self, room_id):
        playFrom = []
        playUrl = []
        url = 'https://api.live.bilibili.com/xlive/web-room/v2/index/getRoomPlayInfo?room_id={0}&no_playurl=0&mask=1&qn=0&platform=web&protocol=0,1&format=0,1,2&codec=0,1&dolby=5&panorama=1'.format(room_id)
        rsp = self._get_sth(url, 'fake')
        jo = json.loads(rsp.text)
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
                            url = format + '_' + codec + '$liveapi2_' + str(qn) + '_' + liveDic['format'][format] + '_' + liveDic['codec'][codec] + '_' + str(room_id)
                            if not api2_playUrl.get(liveDic['qn'][qn]):
                                api2_playUrl[liveDic['qn'][qn]] = []
                            api2_playUrl[liveDic['qn'][qn]].append(url)
                for key, value in api2_playUrl.items():
                    playFrom.append(key)
                    playUrl.append('#'.join(value))
        self.detailContent_args['api2_playFrom'] = playFrom
        self.detailContent_args['api2_playUrl'] = playUrl
        self.get_live_api2_playurl_event.set()

    def live_detailContent(self, array):
        room_id = array[0]
        self.get_live_api2_playurl_event.clear()
        t = threading.Thread(target=self.get_live_api2_playurl, args=(room_id, ))
        t.start()
        url = "https://api.live.bilibili.com/room/v1/Room/get_info?room_id=" + str(room_id)
        rsp = self._get_sth(url, 'fake')
        jRoot = json.loads(rsp.text)
        result = {}
        if jRoot.get('code') == 0:
            jo = jRoot['data']
            self.detailContent_args['mid'] = mid = str(jo["uid"])
            self.get_up_info_event.clear()
            t = threading.Thread(target=self.get_up_info, kwargs={'mid': mid, })
            t.start()
            title = jo['title'].replace("<em class=\"keyword\">", "").replace("</em>", "")
            pic = jo.get("user_cover")
            desc = jo.get('description')
            typeName = jo.get('parent_area_name') + '--' + jo.get('area_name')
            live_status = jo.get('live_status', '')
            if live_status:
                live_status = "开播时间：" + jo.get('live_time')
            else:
                live_status = "未开播"
            vod = {
                "vod_id": room_id,
                "vod_name": title,
                "vod_pic": pic,
                "type_name": typeName,
                "vod_year": "",
                "vod_area": "bililivedanmu",
                "vod_actor": "房间号：" + room_id +  "　UID：" + mid + "　" + live_status,
                "vod_content": desc,
            }
            secondPFrom = ''
            secondP = ''
            if self.userid:
                secondPFrom = '关注Ta'
                first = '是否关注$ '
                follow = '➕关注$1_notplay_follow'
                unfollow = '➖取关$2_notplay_follow'
                secondPList = [first, follow, unfollow]
                secondP = '#'.join(secondPList)
            self.get_live_api2_playurl_event.wait()
            playFrom = self.detailContent_args['api2_playFrom'].copy()
            playUrl = self.detailContent_args['api2_playUrl'].copy()
            if playFrom:
                api1_playFrom = 'API_1'
                api1_playUrl = 'flv线路原画$platform=web&quality=4_' + room_id + '#flv线路高清$platform=web&quality=3_' + room_id + '#h5线路原画$platform=h5&quality=4_' + room_id + '#h5线路高清$platform=h5&quality=3_' + room_id
                playFrom.append(api1_playFrom)
                playUrl.append(api1_playUrl)
            if secondPFrom:
                playFrom.insert(1, secondPFrom)
                playUrl.insert(1, secondP)
            vod['vod_play_from'] = '$$$'.join(playFrom)
            vod['vod_play_url'] = '$$$'.join(playUrl)
            self.get_up_info_event.wait()
            up_info = self.up_info[mid]
            vod["vod_director"] = '🆙 ' + up_info['name']  + "　👥 " + self.zh(jo.get('attention')) + '　' + up_info['following']
            result['list'] = [vod]
        return result

    search_key = ''
    
    def searchContent(self, key, quick):
        if not self.session_fake.cookies:
            t = threading.Thread(target=self.getFakeCookie, args=(True, ))
            t.start()
        self.search_key = key
        self.search_content_dict.clear()
        mid = self.detailContent_args.get('mid', '')
        self.get_up_videos_event.set()
        if quick and mid and not self.get_up_videos_result.get(mid):
            self.get_up_videos_event.clear()
            i = threading.Thread(target=self.get_up_videos, args=(mid, 1, 'quicksearch'))
            i.start()
        types = {'video': '','media_bangumi': '番剧: ', 'media_ft': '影视: ', 'bili_user': '用户: ', 'live': '直播: '}
        for type in types.keys():
            t = threading.Thread(target=self.get_search_content, kwargs={'key': key, 'pg': 1, 'duration_diff': 0, 'order': '', 'type': type, 'ps': self.userConfig['page_size'], })
            t.start()
        result = {'list': []}
        while len(types):
            for type, t in list(self.search_content_dict.items()):
                for r in t:
                    if type == 'video':
                        remark = r['vod_remarks'].split('  💬')
                        r['vod_remarks'] = remark[0]
                    else:
                        r['vod_name'] = types[type] + r['vod_name']
                    result['list'].append(r)
                del self.search_content_dict[type]
                del types[type]
            if len(types):
                with self.con:
                    self.con.wait()
        if quick:
            if mid:
                result['list'] = self.detailContent_args.get('Reply_jump', []) + result['list']
                self.get_up_videos_event.wait()
                result['list'] = self.get_up_videos_result.get(mid, []) + result['list']
                result['list'] = self.detailContent_args.get('interaction', []) + result['list']
            else:
                result['list'] = self.detailContent_args.get('seasons', []) + result['list']
        return result

    heartbeat_con = threading.Condition()
    post_heartbeat_event = threading.Event()
    heartbeat_count = 0

    def stop_heartbeat(self):
        if self.post_heartbeat_event.is_set():
            self.post_heartbeat_event.clear()
            with self.heartbeat_con:
                self.heartbeat_con.notifyAll()

    def post_heartbeat(self, aid, cid, ssid, epid, heartbeat_times, played_time):
        url = 'https://api.bilibili.com/x/click-interface/web/heartbeat'
        data = {'aid': str(aid), 'cid': str(cid), 'csrf': str(self.csrf)}
        if ssid:
            data['sid'] = str(ssid)
            data['epid'] = str(epid)
            data['type'] = 4
        for t in range(heartbeat_times):
            if t == heartbeat_times - 1:
                #播完为-1
                played_time = '-1'
            data['played_time'] = str(played_time)
            self._post_sth(url=url, data=data)
            with self.heartbeat_con:
                self.heartbeat_con.wait()
            if t == heartbeat_times - 1:
                self.post_heartbeat_event.clear()
            if t != heartbeat_times - 1 and not self.post_heartbeat_event.is_set():
                played_time += self.heartbeat_count
                data['played_time'] = str(played_time)
                self._post_sth(url=url, data=data)
            if not self.post_heartbeat_event.is_set():
                break
            played_time += int(self.userConfig['heartbeatInterval'])

    def start_heartbeat(self, aid, cid, ids):
        duration = ssid = epid = ''
        for i in ids:
            if 'ss' in i:
                ssid = i.replace('ss', '')
            if 'ep' in i:
                epid = i.replace('ep', '')
            if 'dur' in i:
                duration = int(i.replace('dur', ''))
        if not duration:
            url = 'https://api.bilibili.com/x/web-interface/view?aid={0}&cid={1}'.format(aid, cid)
            rsp = self._get_sth(url)
            jRoot = json.loads(rsp.text)
            duration = jRoot['data']['duration']
        url = 'https://api.bilibili.com/x/player/v2?aid={0}&cid={1}'.format(aid, cid)
        rsp = self._get_sth(url)
        jo = json.loads(rsp.text)
        data = jo.get('data',{})
        interaction = data.get('interaction', {})
        if interaction.get('graph_version'):
            graph_version = interaction.get('graph_version')
            old = self.detailContent_args.get('graph_version')
            if old != graph_version:
                self.detailContent_args['graph_version'] = graph_version
                t = threading.Thread(target=self.interaction_detailContent)
                t.start()
        played_time = 0
        if int(data.get('last_play_cid', 0)) == int(cid):
            last_play_time = int(data.get('last_play_time'))
            if last_play_time > 0:
                played_time = int(last_play_time / 1000)
        heartbeat_times = int((duration - played_time) / int(self.userConfig['heartbeatInterval'])) + 1
        self.post_heartbeat_event.set()
        t = threading.Thread(target=self.post_heartbeat, args=(aid, cid, ssid, epid, heartbeat_times, played_time, ))
        t.start()
        self.heartbeat_count = 0
        while self.post_heartbeat_event.is_set():
            time.sleep(1)
            self.heartbeat_count += 1
            if self.heartbeat_count == int(self.userConfig['heartbeatInterval']):
                self.heartbeat_count = 0
                with self.heartbeat_con:
                    self.heartbeat_con.notifyAll()

    def _get_sth(self, url, _type='master'):
        if _type == 'vip' and self.session_vip.cookies:
            rsp = self.session_vip.get(url, headers=self.header)
        elif _type == 'fake':
            if not self.session_fake.cookies:
                self.getFakeCookie_event.wait()
            rsp = self.session_fake.get(url, headers=self.header)
        else:
            rsp = self.session_master.get(url, headers=self.header)
        return rsp

    def _post_sth(self, url, data):
        return self.post(url=url, headers=self.header, cookies=self.session_master.cookies, data=data)

    def post_live_history(self, room_id):
        data = {'room_id': str(room_id), 'platform': 'pc', 'csrf': str(self.csrf)}
        url = 'https://api.live.bilibili.com/xlive/web-room/v1/index/roomEntryAction'
        self._post_sth(url=url, data=data)

    def do_notplay(self, ids):
        aid = self.detailContent_args.get('aid')
        mid = self.detailContent_args.get('mid')
        ssid = self.detailContent_args.get('ssid')
        data = {'csrf': str(self.csrf)}
        if 'vodTMPQn' in ids:
            self.detailContent_args['vodTMPQn'] = str(ids[0])
            return
        elif 'follow' in ids:
            if 'special' in ids:
                data.update({'fids': str(mid), 'tagids': str(ids[0])})
                url = 'https://api.bilibili.com/x/relation/tags/addUsers'
            else:
                data.update({'fid': str(mid), 'act': str(ids[0])})
                url = 'https://api.bilibili.com/x/relation/modify'
        elif 'zhui' in ids:
            data.update({'season_id': str(ssid)})
            url = 'https://api.bilibili.com/pgc/web/follow/' + str(ids[0])
        elif 'like' in ids:
            data.update({'aid': str(aid), 'like': str(ids[0])})
            url = 'https://api.bilibili.com/x/web-interface/archive/like'
        elif 'coin' in ids:
            data.update({'aid': str(aid), 'multiply': str(ids[0]), 'select_like': '1'})
            url = 'https://api.bilibili.com/x/web-interface/coin/add'
        elif 'fav' in ids:
            data.update({'rid': str(aid), 'type': '2'})
            data[ids[1] + '_media_ids'] = str(ids[0])
            url = 'https://api.bilibili.com/x/v3/fav/resource/deal'
        elif 'triple' in ids:
            data.update({'aid': str(aid)})
            url = 'https://api.bilibili.com/x/web-interface/archive/like/triple'
        elif 'reply' in ids:
            data.update({'oid': str(ids[0]), 'rpid': str(ids[1]), 'type': '1', 'action': '1'})
            url = 'http://api.bilibili.com/x/v2/reply/action'
        self._post_sth(url=url, data=data)

    def get_cid(self, video):
        url = "https://api.bilibili.com/x/web-interface/view?aid=%s" % str(video['aid'])
        rsp = self._get_sth(url)
        jRoot = json.loads(rsp.text)
        jo = jRoot['data']
        video['cid'] = jo['cid']
        video['duration'] = jo['duration']
        if 'redirect_url' in jo and 'bangumi' in jo['redirect_url']:
            video['ep'] = self.find_bangumi_id(jo['redirect_url'])

    cookie_dic_tmp = {}

    def get_cookies(self, key):
        url = 'https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key=' + key
        rsp = self._get_sth(url, 'fake')
        jo = json.loads(rsp.text)
        if jo['code'] == 0:
            message = jo['data']['message']
            if not message:
                self.cookie_dic_tmp[key] = dict(self.session_fake.cookies)
                t = threading.Thread(target=self.getFakeCookie)
                t.start()
            return message
        return '网络错误'

    def set_cookie(self, key, _type):
        cookie_dic_tmp = self.cookie_dic_tmp.get(key, '')
        if not cookie_dic_tmp:
            message = self.get_cookies(key)
            if message:
                return
        cookie_dic_tmp = self.cookie_dic_tmp.get(key)
        users = self.userConfig.get('users', {})
        users[_type] = {'cookies_dic': cookie_dic_tmp}
        self.getCookie(_type)
        self.dump_config()

    def unset_cookie(self, _type):
        if _type == 'vip':
            self.session_vip.cookies.clear
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
            self.userConfig.pop(str(_List) + '_tmp')
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

    def _checkUpdate(self, action):
        header = {"User-Agent": self.header["User-Agent"]}
        if int(action):
            newVersion = self.userConfig.get('newVersion')
            if newVersion and newVersion['ver'] != self.userConfig['currentVersion']:
                self.userConfig['newVersion']['status'] = '正在更新'
                url = newVersion['url']
                rsp = requests_get(url=url, headers=header, timeout=(2, 5))
                if rsp.status_code == 200:
                    filename = url.split('/')
                    with open(f"{dirname}/{filename[-1]}", 'w', encoding="utf-8") as f:
                        f.write(rsp.text)
                    self.userConfig['newVersion']['status'] = '更新完成'
                else:
                    self.userConfig['newVersion']['status'] = '更新失败'
        else:
            url = 'http://jm92swf.s1002.xrea.com/index.php/update.json'
            rsp = requests_get(url=url, headers=header)
            jo = json.loads(rsp.text)
            ver = jo.get('ver')
            if ver:
                self.userConfig['newVersion'] = jo

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
        '30280': '192000',
        '30232': '132000',
        '30216': '64000',
    }

    def get_dash_media(self, video):
        qnid = str(video.get('id'))
        codecid = video.get('codecid')
        media_codecs = video.get('codecs')
        media_bandwidth = video.get('bandwidth')
        media_startWithSAP = video.get('startWithSap')
        media_mimeType = video.get('mimeType')
        media_BaseURL = video.get('baseUrl').replace('&', '&amp;')
        media_SegmentBase_indexRange = video['SegmentBase'].get('indexRange')
        media_SegmentBase_Initialization = video['SegmentBase'].get('Initialization')
        mediaType = media_mimeType.split('/')
        mediaType = mediaType[0]
        if mediaType == 'video':
            media_frameRate = video.get('frameRate')
            media_sar = video.get('sar')
            media_width = video.get('width')
            media_height = video.get('height')
            media_type_params = f"height='{media_height}' width='{media_width}' frameRate='{media_frameRate}' sar='{media_sar}'"
        elif mediaType == 'audio':
            audioSamplingRate = self.vod_audio_id.get(qnid, '192000')
            media_type_params = f"numChannels='2' sampleRate='{audioSamplingRate}'"
        if codecid:
            qnid += '_' + str(codecid)
        result = f"""
      <Representation id="{qnid}" bandwidth="{media_bandwidth}" codecs="{media_codecs}" mimeType="{media_mimeType}" {media_type_params} startWithSAP="{media_startWithSAP}">
        <BaseURL>{media_BaseURL}</BaseURL>
        <SegmentBase indexRange="{media_SegmentBase_indexRange}">
          <Initialization range="{media_SegmentBase_Initialization}"/>
        </SegmentBase>
      </Representation>"""
        return result

    def get_dash_media_list(self, media_lis):
        mediaType = media_lis[0]['mimeType'].split('/')
        mediaType = mediaType[0]
        defaultQn = defaultCodec = ''
        if mediaType == 'video':
            defaultQn = vodTMPQn = self.detailContent_args.get('vodTMPQn')
            if vodTMPQn:
                vodTMPQn = int(vodTMPQn)
            else:
                defaultQn = str(self.userConfig['vodDefaultQn'])
                vodTMPQn = 120
            defaultCodec = str(self.userConfig['vodDefaultCodec'])
        elif mediaType == 'audio':
            defaultQn = str(self.userConfig['vodDefaultAudio'])
            defaultCodec = '0'
        qn_codec = list(map(lambda x: str(x['id']) + '_' + str(x['codecid']), media_lis))
        Qn_available_lis = []
        #按设定的质量和设定的编码找
        if defaultQn + '_' + defaultCodec in qn_codec:
            Qn_available_lis.append(media_lis[qn_codec.index(defaultQn + '_' + defaultCodec)])
        #按设定的质量找推荐的编码
        if not Qn_available_lis and mediaType == 'video':
            for c in self.vod_codec_id.keys():
                if defaultQn + '_' + str(c) in qn_codec:
                    Qn_available_lis.append(media_lis[qn_codec.index(defaultQn + '_' + str(c))])
        #找4K及以下最高可用画质/音质
        if not Qn_available_lis:
            qn_top = ''
            for q in qn_codec:
                q_c = q.split('_')
                if qn_top and int(qn_top) > int(q_c[0]):
                    break
                elif int(q_c[0]) <= vodTMPQn and mediaType == 'video' and not qn_top or mediaType == 'audio' and not qn_top or int(q_c[0]) == qn_top:
                    qn_top = int(q_c[0])
                    #匹配设定的编码，否则全部
                    if mediaType == 'video' and str(q_c[1]) == defaultCodec:
                        Qn_available_lis = [media_lis[qn_codec.index(str(q))]]
                        break
                    Qn_available_lis.append(media_lis[qn_codec.index(str(q))])
        self.detailContent_args[mediaType] = ''.join(list(map(self.get_dash_media, Qn_available_lis)))
        with self.con:
            self.con.notifyAll()
    
    get_dash_event = threading.Event()
    def get_dash(self, ja):
        duration = ja.get('duration')
        minBufferTime = ja.get('minBufferTime')
        for type in ['video', 'audio']:
            if type in self.detailContent_args:
                self.detailContent_args.pop(type)
            _list = ja.get(type)
            if _list:
                t = threading.Thread(target=self.get_dash_media_list, args=(_list, ))
                t.start()
            else:
                self.detailContent_args[type] = ''
        while True:
            video_list = self.detailContent_args.get('video')
            audio_list = self.detailContent_args.get('audio')
            if video_list != None and audio_list != None:
                break
            with self.con:
                self.con.wait()
        mpd = f"""<MPD xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="urn:mpeg:dash:schema:mpd:2011" xsi:schemaLocation="urn:mpeg:dash:schema:mpd:2011 DASH-MPD.xsd" type="static" mediaPresentationDuration="PT{duration}S" minBufferTime="PT{minBufferTime}S" profiles="urn:mpeg:dash:profile:isoff-on-demand:2011">
  <Period duration="PT{duration}S" start="PT0S">
    <AdaptationSet>
      <ContentComponent contentType="video" id="1"/>{video_list}
    </AdaptationSet>
    <AdaptationSet>
      <ContentComponent contentType="audio" id="2"/>{audio_list}
    </AdaptationSet>
  </Period>
</MPD>"""
        with open(f"{dirname}/playurl.mpd", 'w', encoding="utf-8") as f:
            f.write(mpd)
        self.get_dash_event.set()
        time.sleep(3)
        os.remove(f"{dirname}/playurl.mpd")
        
    def get_durl(self, ja):
        maxSize = -1
        position = -1
        for i in range(len(ja)):
            tmpJo = ja[i]
            if maxSize < int(tmpJo['size']):
                maxSize = int(tmpJo['size'])
                position = i
        url = ''
        if len(ja) > 0:
            if position == -1:
                position = 0
            url = ja[position]['url']
        return url
        
    def playerContent(self, flag, id, vipFlags):
        t = threading.Thread(target=self.stop_heartbeat)
        t.start()
        result = {'playUrl': '', 'url': ''}
        ids = id.split("_")
        if 'web' in id or 'liveapi2' == ids[0]:
            return self.live_playerContent(flag, id, vipFlags)
        if len(ids) < 2:
            return result
        aid = ids[0]
        cid = ids[1]
        if 'setting' in ids:
            if 'liveFilter' in id:
                id = ids[2]
                self.add_cateManualLiveExtra(aid, cid, id)
            elif cid == 'checkUpdate':
                self._checkUpdate(aid)
            elif cid in ['cateManual', 'cateManualLive', 'tuijianList']:
                action = ids[2]
                self.set_normal_cateManual(aid, cid, action)
            elif 'login' in id:
                self.set_cookie(aid, cid)
            elif 'logout' in id:
                self.unset_cookie(aid)
            else:
                self.set_normal_default(aid, cid)
            return result
        elif 'notplay' in ids:
            t = threading.Thread(target=self.do_notplay, args=(ids, ))
            t.start()
            return result
        elif cid == 'cid':
            video = {'aid': str(aid)}
            self.get_cid(video, )
            cid = video['cid']
            ids.append('dur' + str(video['duration']))
            ep = video.get('ep')
            if ep:
                id += '_' + ep
                ids.append(ep)
        url = 'https://api.bilibili.com/x/player/playurl?avid={0}&cid={1}&fnval=4048&fnver=0&fourk=1'.format(aid, cid)
        if 'ep' in id:
            if 'parse' in id:
                test = list(x for x in map(lambda x: x if 'ep' in x else None, ids) if x is not None)
                url = 'https://www.bilibili.com/bangumi/play/' + test[0]
                result["url"] = url
                result["flag"] = 'bilibili'
                result["parse"] = 1
                result['jx'] = 1
                result["header"] = {"User-Agent": self.header["User-Agent"]}
                return result
            url = 'https://api.bilibili.com/pgc/player/web/playurl?aid={0}&cid={1}&fnval=4048&fnver=0&fourk=1'.format(aid, cid)
        # 回传播放历史记录
        if self.userid and int(self.userConfig['heartbeatInterval']):
            t = threading.Thread(target=self.start_heartbeat, args=(aid, cid, ids, ))
            t.start()
        rsp = self._get_sth(url, 'vip')
        jRoot = json.loads(rsp.text)
        if jRoot['code'] == 0:
            if 'data' in jRoot:
                jo = jRoot['data']
            elif 'result' in jRoot:
                jo = jRoot['result']
            else:
                return result
        else:
            return result
        ja = jo.get('dash')
        if ja:
            self.get_dash_event.clear()
            t = threading.Thread(target=self.get_dash, args=(ja, ))
            t.start()
            self.get_dash_event.wait()
            result["url"] = f"{dirname}/playurl.mpd"
        else:
            ja = jo.get('durl')
            result["url"] = self.get_durl(ja)
        result["parse"] = 0
        result["contentType"] = ''
        result["header"] = self.header
        return result

    def live_playerContent(self, flag, id, vipFlags):
        result = {'playUrl': '', 'url': ''}
        ids = id.split("_")
        if len(ids) < 2:
            return result
        # 回传观看直播记录
        if self.userid and int(self.userConfig['heartbeatInterval']) > 0:
            t = threading.Thread(target=self.post_live_history, args=(ids[-1], ))
            t.start()
        if ids[0] == 'liveapi2':
            qn = int(ids[1])
            format = int(ids[2])
            codec = int(ids[3])
            room_id = int(ids[-1])
            url = 'https://api.live.bilibili.com/xlive/web-room/v2/index/getRoomPlayInfo?room_id={0}&protocol=0,1&format={1}&codec={2}&qn={3}&ptype=8&platform=web&dolby=5&panorama=1&no_playurl=0&mask=1'.format(room_id, format, codec, qn)
            rsp = self._get_sth(url, 'fake')
            jo = json.loads(rsp.text)
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
                if ".flv" in playurl:
                    result["contentType"] = 'video/x-flv'
                else:
                    result["contentType"] = ''
            else:
                return result
        else:
            url = 'https://api.live.bilibili.com/room/v1/Room/playUrl?cid=%s&%s' % (ids[1], ids[0])
            # raise Exception(url)
            try:
                rsp = self._get_sth(url)
            except:
                return result
            jRoot = json.loads(rsp.text)
            if jRoot['code'] == 0:
                jo = jRoot['data']
                ja = jo['durl']
                if len(ja) > 0:
                    result["url"] = ja[0]['url']
                if "h5" in ids[0]:
                    result["contentType"] = ''
                else:
                    result["contentType"] = 'video/x-flv'
            else:
                return result
        result["parse"] = 0
        # result['type'] ="m3u8"
        result["header"] = {
            "Referer": "https://live.bilibili.com",
            "User-Agent": self.header["User-Agent"]
        }
        return result

    config = {
        "player": {},
        "filter": {
            "关注": [{"key": "sort", "name": "分类",
                      "value": [{"n": "正在直播", "v": "正在直播"},
                                {"n": "最近关注", "v": "最近关注"}, {"n": "特别关注", "v": "特别关注"},
                                {"n": "悄悄关注", "v": "悄悄关注"}, {"n": "我的粉丝", "v": "我的粉丝"}]}],
            "动态": [{"key": "order", "name": "个人动态排序",
                    "value": [{"n": "最新发布", "v": "pubdate"}, {"n": "最多播放", "v": "click"},
                              {"n": "最多收藏", "v": "stow"}, {"n": "最早发布", "v": "oldest"}]}, ],
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
            "频道": [{"key": "order", "name": "排序",
                    "value": [{"n": "近期热门", "v": "hot"}, {"n": "月播放量", "v": "view"},
                              {"n": "最新投稿", "v": "new"}, {"n": "频道精选", "v": "featured"}, ]}, ],
            "收藏": [{"key": "order", "name": "排序",
                      "value": [{"n": "收藏时间", "v": "mtime"}, {"n": "播放量", "v": "view"},
                                {"n": "投稿时间", "v": "pubtime"}]}, ],
            "历史": [{"key": "type", "name": "分类",
                          "value": [{"n": "视频", "v": "archive"}, {"n": "直播", "v": "live"}, {"n": "UP主", "v": "UP主"}, {"n": "稍后再看", "v": "稍后再看"}]}, ],
            "搜索": [{"key": "type", "name": "类型",
                      "value": [{"n": "视频", "v": "video"}, {"n": "番剧", "v": "media_bangumi"}, {"n": "影视", "v": "media_ft"},
                                {"n": "直播", "v": "live"}, {"n": "用户", "v": "bili_user"}]},
                    {"key": "order", "name": "视频排序",
                      "value": [{"n": "综合排序", "v": "totalrank"}, {"n": "最新发布", "v": "pubdate"}, {"n": "最多点击", "v": "click"},
                                {"n": "最多收藏", "v": "stow"}, {"n": "最多弹幕", "v": "dm"}]},
                    {"key": "duration", "name": "视频时长",
                      "value": [{"n": "全部", "v": "0"}, {"n": "60分钟以上", "v": "4"}, {"n": "30~60分钟", "v": "3"},
                                {"n": "5~30分钟", "v": "2"}, {"n": "5分钟以下", "v": "1"}]}],
        }
    }

    header = {
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://www.bilibili.com',
        'Referer': 'https://www.bilibili.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
    }

    def localProxy(self, param):
        return [200, "video/MP2T", action, ""]
