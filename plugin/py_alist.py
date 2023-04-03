# coding=utf-8
# !/usr/bin/python
import os
import re
import sys
import json
import urllib
import difflib
import requests

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):  # 元类 默认的元类 type
    def getName(self):
        return "Alist"

    def init(self, extend=""):
        print("============{0}============".format(extend))
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        result = {}
        cateManual = {
            "小雅": "http://alist.xiaoya.pro/测试（不限速）",
            "七米蓝": "https://al.chirmyram.com"
        }
        classes = []
        for k in cateManual:
            classes.append({
                'type_name': k,
				"type_flag": "1",
                'type_id': cateManual[k]
            })
        result['class'] = classes
        if (filter):
            filters = {}
            for lk in cateManual:
                link = cateManual[lk]
                filters.update({
                    link: [{"key": "nm", "name": "名        称", "value": [{"n": "复位", "v": ""},{"n": "正序", "v": "False"},{"n": "反序", "v": "True"}]},{"key": "sz", "name": "大        小", "value": [{"n": "复位", "v": ""},{"n": "升序", "v": "False"},{"n": "降序", "v": "True"}]},{"key": "tp", "name": "类        型", "value": [{"n": "复位", "v": ""},{"n": "升序", "v": "False"},{"n": "降序", "v": "True"}]},{"key": "tm", "name": "修改时间", "value": [{"n": "复位", "v": ""},{"n": "升序", "v": "False"},{"n": "降序", "v": "True"}]},{"key": "xq", "name": "详情模式", "value": [{"n": "默认", "v": "150"},{"n": "单文件", "v": "1"},{"n": "全排列", "v": "0"}]}]
                })
            result['filters'] = filters
        return result

    def get_homeVideoContent(self, tidDict):
        videos = []
        isfolder = True
        tid = tidDict['type_id']
        try:
            res = self.categoryContent(tid, pg=1, filter=False, extend={})
        except:
            return {}, False
        if 'type_flag' in tidDict and len(res) !=0:
            resList = res['list']
            result = {}
            for rL in resList:
               if rL['vod_tag'] == 'file':
                   videos.append(rL)
            result['list'] = videos
            result['page'] = 1
            result['pagecount'] = 1
            result['limit'] = 999
            result['total'] = 999999
        elif len(res) ==0:
            isfolder = False
            result = {}
        else:
            isfolder = False
            result = res
        if len(videos) == 0:
            result = res
        else:
            if '+++' in result['list'][0]['vod_id']:
                isfolder = False
        return result, isfolder

    def homeVideoContent(self):
        tidDict = self.homeContent(False)['class'][0]
        result, isfolder = self.get_homeVideoContent(tidDict)
        while isfolder:
            tidDict = {'type_flag': '1', 'type_id': result['list'][0]['vod_id']}
            result, isfolder = self.get_homeVideoContent(tidDict)
        return result

    ver = ''
    baseurl = ''
    def getVersion(self, gtid):
        if gtid.count('/') == 2:
            gtid = gtid + '/'
        baseurl = re.findall(r"http.*://.*?/", gtid)[0]
        header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
            'Referer': baseurl
        }
        ver = self.fetch(baseurl + 'api/public/settings', headers=header)
        vjo = json.loads(ver.text)['data']
        if type(vjo) is dict:
            ver = 3
        else:
            ver = 2
        self.ver = ver
        self.baseurl = baseurl

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        if '^^^' in tid:
            username = tid.split('^^^')[1]
            password = tid.split('^^^')[2]
            tid = tid.split('^^^')[0]
        else:
            username = ''
            password = ''
        if tid.count('/') == 2:
            tid = tid + '/'
        nurl = re.findall(r"http.*://.*?/", tid)[0]
        if self.ver == '' or self.baseurl != nurl:
            self.getVersion(tid)
        ver = self.ver
        baseurl = self.baseurl
        header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
            'Referer': baseurl
        }
        token = requests.get('http://www.lmhome.tk:8151/cache',params={'key': 'alisttoken'}).text
        if password != '' and username != '' and 'Authorization' not in header.keys():
            if token != '':
                header.update({'Authorization': token})
            else:
                logurl = baseurl + 'api/auth/login'
                logparam = {
                    'username': username,
                    'password': password
                }
                r = requests.post(logurl, json=logparam, headers=header)
                jo = json.loads(r.text)
                if jo['code'] == 200:
                    token = jo['data']['token']
                    header.update({'Authorization': token})
                else:
                    token = ''
                value = token
                requests.post('http://www.lmhome.tk:8151/cache', params={'key': 'alisttoken', }, data=value, headers={'Content-Length': str(len(value))})
        if tid.count('/') == 2:
            tid = tid + '/'
        pat = tid.replace(baseurl,"")
        param = {
            "path": '/' + pat
        }
        if ver == 2:
            rsp = self.postJson(baseurl + 'api/public/path', param, headers=header)
            jo = json.loads(rsp.text)
            vodList = jo['data']['files']
        elif ver == 3:
            rsp = self.postJson(baseurl + 'api/fs/list', param, headers=header)
            jo = json.loads(rsp.text)
            vodList = jo['data']['content']
        ovodList = vodList
        numkey = 150
        if len(extend) != 0:
            if 'tp' in extend and extend['tp'] != '':
                fl = 'type'
                if extend['tp'] == "True":
                    key = True
                if extend['tp'] == "False":
                    key = False
                vodList.sort(key=lambda x: (x['{0}'.format(fl)]), reverse=key)
            elif 'sz' in extend and extend['sz'] != '':
                fl = 'size'
                if extend['sz'] == "True":
                    key = True
                if extend['sz'] == "False":
                    key = False
                vodList.sort(key=lambda x: (x['{0}'.format(fl)]), reverse=key)
            elif 'nm' in extend and extend['nm'] != '':
                fl = 'name'
                if extend['nm'] == "True":
                    key = True
                if extend['nm'] == "False":
                    key = False
                vodList.sort(key=lambda x: (x['{0}'.format(fl)]), reverse=key)
            elif 'tm' in extend and extend['tm'] != '':
                if ver == 2:
                    fl = 'updated_at'
                elif ver == 3:
                    fl = 'modified'
                if extend['tm'] == "True":
                    key = True
                if extend['tm'] == "False":
                    key = False
                vodList.sort(key=lambda x: (x['{0}'.format(fl)]), reverse=key)
            elif 'xq' in extend:
                if extend['xq'] != "0":
                    numkey = int(extend['xq'])
                else:
                    numkey = 9999
            else:
                vodList = ovodList
        else:
            vodList = ovodList
        videos = []
        cid = ''
        purl = ''
        svodList = str(vodList)
        lenvodList = len(vodList)
        nameList = re.findall(r"\'name\': \'(.*?)\'", svodList)
        substr = str(nameList)
        foldernum = svodList.count('\'type\': 1')
        filenum = lenvodList - foldernum
        for vod in vodList:
            if ver == 2:
                img = vod['thumbnail']
            elif ver == 3:
                img = vod['thumb']
            if len(img) == 0:
                if vod['type'] == 1:
                    img = "http://img1.3png.com/281e284a670865a71d91515866552b5f172b.png"
            if pat != '':
                aid = pat + '/'
            else:
                aid = pat
            if vod['type'] == 1:
                tag = "folder"
                remark = "文件夹"
                cid = baseurl + aid + vod['name']
            #计算文件大小
            elif os.path.splitext(vod['name'])[1] in ['.mp4', '.mkv', '.ts', '.TS', '.avi', '.flv', '.rmvb', '.mp3', '.flac', '.wav', '.wma', '.dff']:
                size = vod['size']
                if size > 1024 * 1024 * 1024 * 1024.0:
                    fs = "TB"
                    sz = round(size / (1024 * 1024 * 1024 * 1024.0), 2)
                elif size > 1024 * 1024 * 1024.0:
                    fs = "GB"
                    sz = round(size / (1024 * 1024 * 1024.0), 2)
                elif size > 1024 * 1024.0:
                    fs = "MB"
                    sz = round(size / (1024 * 1024.0), 2)
                elif size > 1024.0:
                    fs = "KB"
                    sz = round(size / (1024.0), 2)
                else:
                    fs = "KB"
                    sz = round(size / (1024.0), 2)
                tag = "file"
                remark = str(sz) + fs
                cid = baseurl + aid + vod['name']
                # 开始爬视频与字幕
                if filenum < numkey:
                    vodurl = vod['name']
                    # 开始爬字幕
                    cid = '###'
                    subname = re.findall(r"(.*)\.", vod['name'])[0]
                    if filenum == 2:
                        if '.ass' in substr:
                            sub = difflib.get_close_matches('.ass', nameList, 1, cutoff=0.1)
                            if len(sub) != 0:
                                sub = sub[0]
                            else:
                                sub = ''
                            if sub.endswith('.ass'):
                                subt = '@@@' + sub
                        if '.srt' in substr:
                            sub = difflib.get_close_matches('.srt', nameList, 1, cutoff=0.1)
                            if len(sub) != 0:
                                sub = sub[0]
                            else:
                                sub = ''
                            if sub.endswith('.srt'):
                                subt = '@@@' + sub
                    else:
                        if '.ass' in substr:
                            sub = difflib.get_close_matches('{0}.ass'.format(subname), nameList, 1, cutoff=0.1)
                            if len(sub) != 0:
                                sub = sub[0]
                            else:
                                sub = ''
                            if subname in sub and sub.endswith('.ass'):
                                subt = '@@@' + sub
                        elif '.srt' in substr:
                            sub = difflib.get_close_matches('{0}.srt'.format(subname), nameList, 1, cutoff=0.1)
                            if len(sub) != 0:
                                sub = sub[0]
                            else:
                                sub = ''
                            if subname in sub and sub.endswith('.srt'):
                                subt = '@@@' + sub
                    # 合并链接
                    if 'subt' in locals().keys():
                        purl = purl + '{0}{1}##'.format(vodurl, subt)
                    else:
                        purl = purl + '{0}##'.format(vodurl)
                else:
                    subname = re.findall(r"(.*)\.", vod['name'])[0]
                    if '.ass' in substr:
                        sub = difflib.get_close_matches('{0}.ass'.format(subname), nameList, 1, cutoff=0.1)
                        if len(sub) != 0:
                            sub = sub[0]
                        else:
                            sub = ''
                        if subname in sub and sub.endswith('.ass'):
                            subt = '@@@' + sub
                            cid = cid + subt
                    elif '.srt' in substr:
                        sub = difflib.get_close_matches('{0}.srt'.format(subname), nameList, 1, cutoff=0.1)
                        if len(sub) != 0:
                            sub = sub[0]
                        else:
                            sub = ''
                        if subname in sub and sub.endswith('.srt'):
                            subt = '@@@' + sub
                            cid = cid + subt
            else:
                continue
            if password != '' and username != '' and cid != '###':
                cid = '{}^^^{}^^^{}'.format(cid, username, password)
            videos.append({
                "vod_id":  cid,
                "vod_name": vod['name'],
                "vod_pic": img,
                "vod_tag": tag,
                "vod_remarks": remark
            })
        if 'purl' in locals().keys():
            purl = baseurl + aid + '+++' + purl
            for v in videos:
                if v['vod_id'] == '###':
                    if password != '' and username != '' and '^^^' not in purl:
                        purl = '{}^^^{}^^^{}'.format(purl, username, password)
                    v['vod_id'] = purl
        result['list'] = videos
        result['page'] = 1
        result['pagecount'] = 1
        result['limit'] = 999
        result['total'] = 999999
        return result

    def detailContent(self, array):
        id = array[0]
        if '+++' in id:
            ids = id.split('+++')
            durl = ids[0]
            if '^^^' in ids[1]:
                infos = ids[1].split('^^^')
                username = infos[1]
                password = infos[2]
                append = '^^^{}^^^{}'.format(username, password)
            else:
                infos = ids[1]
                append = ''
            vsList = infos.strip('##').split('##')
            vsurl = ''
            for vs in vsList:
                if '@@@' in vs:
                    dvs = vs.split('@@@')
                    vname = dvs[0].replace('#','-')
                    vurl = durl + dvs[0].replace('#','---')
                    surl = durl + dvs[1].replace('#','---')
                    vsurl = vsurl + '{0}${1}@@@{2}{3}#'.format(vname, vurl, surl, append)
                else:
                    vurl = durl + vs.replace('#','---')
                    vsurl = vsurl + '{0}${1}{2}#'.format(vs.replace('#','-'), vurl, append)
            url = vsurl
        else:
            durl = id.replace('#','-')
        if self.ver == '' or self.baseurl == '':
            self.getVersion(durl)
        baseurl = self.baseurl
        if '+++' in id:
            vid = durl.replace(baseurl, "").strip('/')
        else:
            vid = durl.replace(re.findall(r".*/", durl)[0], "")
            url = vid + '$' + id.replace('#','---') + append
        vod = {
            "vod_id": vid,
            "vod_name": vid,
            "vod_pic": '',
            "vod_tag": '',
            "vod_play_from": "播放",
            "vod_play_url": url
        }
        result = {
            'list': [
                vod
            ]
        }
        return result

    def searchContent(self, key, quick):
        result = {
            'list': []
        }
        return result

    def playerContent(self, flag, id, vipFlags):
        requests.delete('http://www.lmhome.tk:8151/cache', params={'key': 'alisttoken'})
        result = {}
        url = ''
        subturl = ''
        if '^^^' in id:
            infos = id.split('^^^')
            username = infos[1]
            password = infos[2]
            id = infos[0]
        else:
            username = ''
            password = ''
        id = id.replace('---','#')
        ifsub = '@@@' in id
        if ifsub is True:
            ids = id.split('@@@')
            if self.ver == '' or self.baseurl == '':
                self.getVersion(ids[1])
            ver = self.ver
            baseurl = self.baseurl
            header = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
                'Referer': baseurl
            }
            token = requests.get('http://www.lmhome.tk:8151/cache', params={'key': 'alisttoken'}).text
            if password != '' and username != '' and 'Authorization' not in header.keys():
                if token != '':
                    header.update({'Authorization': token})
                else:
                    logurl = baseurl + 'api/auth/login'
                    logparam = {
                        'username': username,
                        'password': password
                    }
                    r = requests.post(logurl, json=logparam, headers=header)
                    jo = json.loads(r.text)
                    if jo['code'] == 200:
                        token = jo['data']['token']
                        header.update({'Authorization': token})
                    else:
                        token = ''
            fileName = ids[1].replace(baseurl, "")
            vfileName = ids[0].replace(baseurl, "")
            param = {
                "path": '/' + fileName,
                "password": "",
                "page_num": 1,
                "page_size": 100
            }
            vparam = {
                "path": '/' + vfileName,
                "password": "",
                "page_num": 1,
                "page_size": 100
            }
            if ver == 2:
                rsp = self.postJson(baseurl + 'api/public/path', param, headers=header)
                jo = json.loads(rsp.text)
                vodList = jo['data']['files'][0]
                subturl = vodList['url']
                vrsp = self.postJson(baseurl + 'api/public/path', vparam, headers=header)
                vjo = json.loads(vrsp.text)
                vList = vjo['data']['files'][0]
                url = vList['url']
            elif ver == 3:
                rsp = self.postJson(baseurl + 'api/fs/get', param, headers=header)
                jo = json.loads(rsp.text)
                vodList = jo['data']
                subturl = vodList['raw_url']
                vrsp = self.postJson(baseurl + 'api/fs/get', vparam, headers=header)
                vjo = json.loads(vrsp.text)
                vList = vjo['data']
                url = vList['raw_url']
            if subturl.startswith('http') is False:
                head = re.findall(r"h.*?:", baseurl)[0]
                subturl = head + subturl
            if url.startswith('http') is False:
                head = re.findall(r"h.*?:", baseurl)[0]
                url = head + url
            urlfileName = urllib.parse.quote(fileName)
            subturl = subturl.replace(fileName, urlfileName)
            urlvfileName = urllib.parse.quote(vfileName)
            url = url.replace(vfileName, urlvfileName)
            result['subt'] = subturl
        else:
            if self.ver == '' or self.baseurl == '':
                self.getVersion(id)
            ver = self.ver
            baseurl = self.baseurl
            header = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
                'Referer': baseurl
            }
            token = requests.get('http://www.lmhome.tk:8151/cache', params={'key': 'alisttoken'}).text
            if password != '' and username != '' and 'Authorization' not in header.keys():
                if token != '':
                    header.update({'Authorization': token})
                else:
                    logurl = baseurl + 'api/auth/login'
                    logparam = {
                        'username': username,
                        'password': password
                    }
                    r = requests.post(logurl, json=logparam, headers=header)
                    jo = json.loads(r.text)
                    if jo['code'] == 200:
                        token = jo['data']['token']
                        header.update({'Authorization': token})
                    else:
                        token = ''
            vfileName = id.replace(baseurl, "")
            vparam = {
                "path": '/' + vfileName,
                "password": "",
                "page_num": 1,
                "page_size": 100
            }
            if ver == 2:
                vrsp = self.postJson(baseurl + 'api/public/path', vparam, headers=header)
                vjo = json.loads(vrsp.text)
                vList = vjo['data']['files'][0]
                driver = vList['driver']
                url = vList['url']
            elif ver == 3:
                vrsp = self.postJson(baseurl + 'api/fs/get', vparam, headers=header)
                vjo = json.loads(vrsp.text)
                vList = vjo['data']
                url = vList['raw_url']
                driver = vList['provider']
            if url.startswith('http') is False:
                head = re.findall(r"h.*?:", baseurl)[0]
                url = head + url
            urlvfileName = urllib.parse.quote(vfileName)
            url = url.replace(vfileName, urlvfileName)
        result["parse"] = 0
        result["playUrl"] = ''
        result["url"] = url

        return result

    flurl = ''
    config = {
        "player": {},
        "filter": {}
    }
    header = {}

    def localProxy(self, param):
        return [200, "video/MP2T", action, ""]