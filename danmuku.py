import re
import time
import json
import base64
import hashlib
import requests
from zlib import decompress
from bs4 import BeautifulSoup

class DanmakuItem(object):
    def __init__(self, timeOffset, content):
        self.timeOffset = "{:.5f}".format(timeOffset)
        self.content = content.replace('\n', ' ')

def handleDanmu(params):
    erro = False
    yield """<i>
 <chatserver>YingShi</chatserver>
 <chatid>0000000</chatid>
 <mission>0</mission>
 <maxlimit>500</maxlimit>
 <state>0</state>
 <real_name>0</real_name>
 <source>k-v</source>"""
    try:
        url = 'https://dmku.thefilehosting.com/?ac=dm&url=' + params['url']
        r = requests.get(url, headers=header, timeout=15)
        items = r.json()['danmuku'][2:]
    except:
        erro = True
    if erro:
        maxRow = 10
        rowToNext = [0 for _ in range(maxRow)]
        items = getDanmukuItems(params)
        for item in items:
            item.content = removeEmoji(item.content)
            if len(item.content) == 0:
                continue
            start = float(item.timeOffset)
            for row in range(maxRow):
                if start >= rowToNext[row]:
                    rowToNext[row] = int(start + len(item.content) * 0.25 + 2.5)
                    yield ' <d p="{},1,25,16777215">{}</d>'.format(item.timeOffset, item.content)
                    break
    else:
        for item in items:
            content = removeEmoji(item[4])
            if len(content) == 0:
                continue
            yield ' <d p="{:.5f},1,25,16777215">{}</d>'.format(item[0], content)
    yield """</i>"""

def getDanmukuItems(params):
    url = params['url']
    platform = params['platform']
    if platform == 'qq':
        return getQqItems(url)
    elif platform == 'mgtv':
        return getMgtvItems(url)
    elif platform == 'iqiyi':
        return getIqiyiItems(url)
    elif platform == 'youku':
        return getYoukuItems(url)
    else:
        return ''

def getQqItems(url):
    m = re.search(r'://v.qq.com/x/cover/(?:.*/)?(\w+).html', url)
    vid = m.group(1)
    r = requests.get(url, headers=header, timeout=15)
    m = re.search(r"duration\":(\d+)", r.text)
    videoDuration = int(m.group(1))
    for i in range(0, videoDuration * 1000, 30000):
        if i > videoDuration * 1000:
            break
        url = 'https://dm.video.qq.com/barrage/segment/{}/t/0/{}/{}'.format(vid, i, i + 30000)
        r = requests.get(url, headers=header, timeout=15)
        if r.status_code != 200:
            break
        for item in r.json()['barrage_list']:
            yield DanmakuItem(int(item['time_offset'])/1000, item['content'])

def getMgtvItems(url):
    m = re.search(r'://www.mgtv.com/b/(\d+)/(\d+).html', url)
    cid = m.group(1)
    vid = m.group(2)
    r = requests.get(url, headers=header, timeout=15)
    mList = re.findall(r",\"(?:(\d{1,2}):)?(\d{1,2}):(\d{1,2})\"", r.text)
    hour = 0
    min = 0
    sec = 0
    for m in mList:
        hour = m[0]
        min = m[1]
        sec = m[2]
        if int(min) > 10 or hour != '':
            break
    videoDuration = int(sec)
    videoDuration += int(min) * 60
    if hour != '':
        videoDuration += int(hour) * 3600
    vtime = 0
    params = {
        'cid': cid,
        'vid': vid,
        'time': vtime
    }
    while vtime <= videoDuration * 1000:
        r = requests.get('https://galaxy.bz.mgtv.com/rdbarrage', params=params, headers=header, timeout=15)
        if r.status_code != 200:
            break
        data = r.json()
        if data['status'] != 0:
            break
        items = data['data']['items']
        if items:
            itemList = sorted(data['data']['items'], key=lambda x: x['time'])
            for item in itemList:
                yield DanmakuItem(int(item['time'])/1000, item['content'])
        vtime = data['data']['next']

def getIqiyiItems(url):
    r = requests.get(url, headers=header, timeout=15)
    m = re.search(r"\"tvId\":(\d+),", r.text)
    tvid = m.group(1)
    hour = 0
    min = 0
    sec = 0
    mList = re.findall(r"\"duration\":\"(?:(\d{1,2}):)?(\d{2}):(\d{2})\"", r.text)
    for m in mList:
        hour = m[0]
        min = m[1]
        sec = m[2]
        if int(min) > 10 or hour != '':
            break
    videoDuration = int(sec)
    videoDuration += int(min) * 60
    if hour != '':
        videoDuration += int(hour) * 3600
    for i in range(1, int(videoDuration / 300 + 2), 1):
        url = 'https://cmts.iqiyi.com/bullet/{}/{}/{}_300_{}.z'.format(tvid[-4:-2], tvid[-2:], tvid, i)
        r = requests.get(url, headers=header, timeout=15)
        data = decompress(r.content)
        soup = BeautifulSoup(data.decode(), 'html.parser')
        for item in soup.select('bulletinfo'):
            vtime = int(item.find('showtime').text)
            content = item.find('content').text
            yield DanmakuItem(vtime, content)

def getYoukuItems(url):
    s = requests.Session()
    m = re.search(r'://v.youku.com/v_show/id_([\w=]+).html', url)
    vid = m.group(1)
    app_key = '24679788'
    guid = 'NJnMGnrls3wCAXQaiNsMGIsY'
    r = s.get('https://acs.youku.com/h5/mtop.youku.favorite.query.isfavorite/1.0/', params={'appKey': app_key}, headers=header, timeout=15)
    m = re.search(r'_m_h5_tk=(\w+)_', r.headers['Set-Cookie'])
    token = m.group(1)
    emptyMats = 0
    for mat in range(120):
        t = int(time.time()) * 1000
        msg = base64.b64encode(json.dumps({"ctime": t, "ctype": 10004, "cver": "v1.0", "guid": guid, "mat": mat, "mcount": 1, "pid": 0, "sver": "3.1.0", "vid": vid}).encode()).decode()
        data = {'pid': 0, 'ctype': 10004, 'sver': '3.1.0', 'cver': 'v1.0', 'ctime': t, 'guid': guid, 'vid': vid, "mat": mat, "mcount": 1, "type": 1, 'msg': msg}
        data['sign'] = hashlib.md5((msg + 'MkmC9SoIw6xCkSKHhJ7b5D2r51kBiREr').encode()).hexdigest()
        data = json.dumps(data)
        params = {'jsv': '2.7.0', 'appKey': app_key, 't': t, 'api': 'mopen.youku.danmu.list', 'v': '1.0', 'type': 'originaljson', 'dataType': 'jsonp', 'timeout': 20000, 'jsonpIncPrefix': 'utility'}
        params['sign'] = hashlib.md5('{}&{}&{}&{}'.format(token, t, app_key, data).encode()).hexdigest()
        r = s.post('https://acs.youku.com/h5/mopen.youku.danmu.list/1.0/', data={'data': data}, params=params, headers=header, timeout=15)
        result = json.loads(r.json()['data']['result'])
        if result['code'] != 1:
            break
        items = sorted(result['data']['result'], key=lambda x: x['playat'])
        if len(items) == 0:
            emptyMats += 1
            if emptyMats >= 5:
                break
            continue
        else:
            emptyMats = 0
        for item in items:
            yield DanmakuItem(item['playat']/1000, item['content'])

header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.54 Safari/537.36"
    }

def removeEmoji(src):
    regrexPattern = re.compile(
        pattern="["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        u"\U00002500-\U00002BEF"  # chinese char
        u"\U00002702-\U000027B0"
        u"\U00002702-\U000027B0"
        u"\U0001f926-\U0001f937"
        u"\U00010000-\U0010ffff"
        u"\u2640-\u2642"
        u"\u2600-\u2B55"
        u"\u200d"
        u"\u23cf"
        u"\u23e9"
        u"\u231a"
        u"\ufe0f"  # dingbats
        u"\u3030"
        u"\b"
        "]+",
        flags=re.UNICODE)
    content = regrexPattern.sub(r'', src)
    patternDict = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "\'": "&apos;"
    }
    for key in patternDict:
        content = re.sub(r'{}'.format(key), patternDict[key], content)
    return content