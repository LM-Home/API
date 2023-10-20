import os
import re
import json
import time
import difflib
import uvicorn
import requests
from PIL import Image
from lxml import etree
from io import BytesIO
from ddddocr import DdddOcr
from urllib.parse import quote, unquote
from base64 import b64decode, b64encode
from fastapi import Body, FastAPI, Request, HTTPException
from fastapi.responses import Response, HTMLResponse, FileResponse, StreamingResponse
from danmuku import handleDanmu

# OCR相关
def handleOcr(img: bytes, comp, lenth):
    retry = 1
    ocr = DdddOcr(show_ad=False)
    while retry < 5:
        result = ocr.classification(img)
        if comp == 'digit':
            if result.isdigit():
                if lenth != 0:
                    if len(result) == lenth:
                        break
                else:
                    break
        elif comp == 'alpha':
            if result.isalpha():
                if lenth != 0:
                    if len(result) == lenth:
                        break
                else:
                    break
        elif comp == 'alnum':
            if result.isalnum():
                if lenth != 0:
                    if len(result) == lenth:
                        break
                else:
                    break
        else:
            raise ValueError("识别结果格式或位数错误")
        retry += 1
    return result

def handleDet(img: bytes):
    det = DdddOcr(det=True, show_ad=False)
    return det.detection(img)

def handleCrop(img):
    imgByte = BytesIO()
    img.save(imgByte, format='PNG', subsampling=0, quality=100)
    imgByte = imgByte.getvalue()
    return imgByte

def handleSlide(targetImg: bytes, backgroundImg: bytes):
    slide = DdddOcr(det=False, ocr=False, show_ad=False)
    if len(backgroundImg) == 0:
        imageStream = BytesIO(targetImg)
        imageFile = Image.open(imageStream)
        backgroundImg = imageFile.crop((0, 300, 240, 450))
        cropped = imageFile.crop((0, 0, 240, 150))
        return slide.slide_comparison(handleCrop(cropped), handleCrop(backgroundImg))
    else:
        return slide.slide_match(targetImg, backgroundImg, simple_target=True)

# 开始FastAPI及相关设置
temp = {}
cache = {}
PythonT4 = FastAPI()
# 提供 index.html 文件
@PythonT4.get("/", response_class=HTMLResponse)
def index():
    return FileResponse("templates/index.html")

@PythonT4.get("/files/{filePath:path}", response_class=HTMLResponse)
def downloadFile(filePath: str):
    content = f"""<!DOCTYPE html>
<html>
  <head>
    <title>文件</title>
  </head>
  <body>
  <h1>文件</h1><hr><pre><a href="/files/{filePath[:filePath.rfind('/')]}" style="font-size: 20px; text-decoration: none;">返回上级目录</a>\n"""
    filePath = 'files/{}'.format(filePath)
    infoList = []
    if os.path.isdir(filePath):
        fileList = os.listdir(filePath)
    else:
        return FileResponse(filePath)
    for file in fileList:
        if os.path.isdir(filePath+'/'+file):
            type = 0
        else:
            type = 1
        infoList.append({'name': file, 'type': type})
    infoList = sorted(infoList, key=lambda x: x['type'])
    for info in infoList:
        content += '<a href={}/{} style="font-size: 20px; text-decoration: none;" >{}</a>\n'.format(filePath, info['name'], info['name']).replace('//', '/')
    content += """  </pre><hr></body>
</html>"""
    return content

@PythonT4.get("/PythonT4", response_class=HTMLResponse)
def indexT4():
    return FileResponse("templates/index.html")

# 设置网页图标
@PythonT4.get("/favicon.ico")
def favicon():
    return FileResponse("templates/favicon.ico")

# PythonT4弹幕
@PythonT4.get("/danmu")
def danmu(params: str):
    try:
        tempkey = params
        params = json.loads(params)
        def getContent(params):
            content = ''
            starttime = int(time.time())
            for line in handleDanmu(params):
                yield (line + '\n').encode()
                content = content + line + '\n'
                if line == '</i>':
                    temp.update({tempkey: {'content': content, 'expire_at': int(time.time()) + 14400}})
                    break
                if int(time.time()) - starttime >= 600:
                    break
        if tempkey in temp:
            if temp[tempkey]['expire_at'] >= int(time.time()):
                content = temp[tempkey]['content']
                return Response(content=content, media_type="text/xml")
            else:
                del temp[tempkey]
                return StreamingResponse(getContent(params), 200, {'Content-Type': 'text/xml'})
        else:
            return StreamingResponse(getContent(params), 200, {'Content-Type': 'text/xml'})
    except Exception as e:
        raise HTTPException(status_code=404, detail="错误：{}".format(e))

# PythonT4搜索弹幕
@PythonT4.get("/searchdm")
def searchdm(params: str):
    params = json.loads(params)
    pos = params['pos']
    name = params['name']
    pos = int(pos)
    pos = pos - 1
    if pos < 0:
        pos = 0
    name = name.replace(' ', '+')
    try:
        url = 'https://v.qq.com/x/search/?q={}'.format(name)
        header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.54 Safari/537.36'}
        r = requests.get(url, headers=header, timeout=5)
        html = etree.HTML(r.content.decode())
        vodList = html.xpath("//div[@class='mix_warp']/div")
        diffList = []
        for vod in vodList:
            diffList.append(difflib.SequenceMatcher(None, re.search(r'&title_txt=(.*)', vod.xpath(".//h2[contains(@class,'result_title')]/@dt-params")[0]).group(1), name).ratio())
        infosList = html.xpath("//div[@class='mix_warp']/div")[diffList.index(max(diffList))].xpath(".//div[@class='item item_fold']/a")
        if infosList == []:
            try:
                platform = re.search(r'site_id=(.*?)&', html.xpath("//div[@class='mix_warp']/div")[diffList.index(max(diffList))].xpath(".//div[@class='item']")[pos].xpath("./a/@dt-params")[0]).group(1)
                danmuUrl = html.xpath("//div[@class='mix_warp']/div")[diffList.index(max(diffList))].xpath(".//div[@class='item']")[pos].xpath("./a/@href")[0]
            except:
                platform = re.search(r'site_id=(.*?)&', html.xpath("//div[@class='mix_warp']/div")[diffList.index(max(diffList))].xpath(".//div[@class='result_btn_line']")[pos].xpath("./a/@dt-params")[0]).group(1)
                danmuUrl = html.xpath("//div[@class='mix_warp']/div")[diffList.index(max(diffList))].xpath(".//div[@class='result_btn_line']")[pos].xpath("./a/@href")[0]
        else:
            platform = re.search(r'&site_id=(.*?)&', infosList[0].xpath("./@dt-params")[0]).group(1)
            pid = re.search(r'&id=(.*?)&', infosList[0].xpath("./@dt-params")[0]).group(1)
            asyncparam = infosList[0].xpath("./@data-asyncparam")[0]
            url = 'https://pbaccess.video.qq.com/trpc.videosearch.search_cgi.http/load_playsource_list_info?pageNum=0&id={}&dataType=2&pageContext={}&scene=2&platform=2&appId=10718&site={}&vappid=34382579&vsecret=e496b057758aeb04b3a2d623c952a1c47e04ffb0a01e19cf&g_tk=&g_vstk=&g_actk='.format(pid, quote(asyncparam), platform)
            danmuUrl = \
            requests.get(url, headers=header, timeout=5).json()['data']['normalList']['itemList'][0]['videoInfo']['firstBlockSites'][0]['episodeInfoList'][pos]['url']
        params = {}
        if platform != 'qq':
            danmuUrl = unquote(re.search(r'&url=(.*)', danmuUrl).group(1))
        if 'qq.com' in danmuUrl:
            params = {'platform': 'qq', 'url': danmuUrl}
        elif 'mgtv.com' in danmuUrl:
            params = {'platform': 'mgtv', 'url': danmuUrl}
        elif 'iqiyi.com' in danmuUrl:
            params = {'platform': 'iqiyi', 'url': danmuUrl}
        elif 'youku.com' in danmuUrl:
            params = {'platform': 'youku', 'url': danmuUrl}
        return Response(content=json.dumps(params), media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=404, detail="错误：{}".format(e))

# 设置缓存
@PythonT4.post("/cache")
async def setCache(request: Request, key: str):
    value = await request.body()
    cache[key] = value

# 获取缓存
@PythonT4.get("/cache")
async def getCache(key: str):
    if key not in cache:
        return Response(content='', media_type="text/plain")
    try:
        if type(cache[key]) == dict or type(cache[key]) == list:
            content = json.dumps(cache[key])
        else:
            content = cache[key]
        return Response(content=content, media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=404, detail="错误：{}".format(e))

# 删除缓存
@PythonT4.delete("/cache")
async def deleteCache(key: str):
    if key not in cache:
        raise HTTPException(status_code=404, detail="无法删除，未找到缓存{}".format(key))
    del cache[key]

# ocr 处理
@PythonT4.post("/ocr")
def ocr(data: dict = Body(...)):
    cookies = {}
    backgroundImgdata = bytes()
    # 获取验证码及所需headers
    if 'header' in data:
        header = data['header']
    else:
        header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.54 Safari/537.36'
        }
    if 'urlList' in data:
        # 为url则下载并获取cookies
        urlList = data['urlList']
        try:
            if len(urlList) == 1:
                r = requests.get(urlList[0], headers=header, timeout=30)
                for key, value in r.cookies.items():
                    cookies.update({key: value})
                imgdata = r.content
            else:
                imgdata = requests.get(urlList[0], headers=header, timeout=30).content
                backgroundImgdata = requests.get(urlList[1], headers=header, timeout=30).content
        except:
            return {'code': 0, 'result': None, 'msg': '访问{}超时'.format(urlList)}
    elif 'imgList' in data:
        # 为imgList中为imgs的base64解码
        imgList = data['imgList']
        if len(imgList) == 1:
            imgdata = imgList[0]
            if imgdata.startswith('data'):
                imgdata = imgdata.split(',', 1)[1]
            imgdata = b64decode(imgdata)
        else:
            imgdata = imgList[0]
            if imgdata.startswith('data'):
                imgdata = imgdata.split(',', 1)[1]
            imgdata = b64decode(imgdata)
            backgroundImgdata = imgList[1]
            if backgroundImgdata.startswith('data'):
                backgroundImgdata = backgroundImgdata.split(',', 1)[1]
            backgroundImgdata = b64decode(backgroundImgdata)
    else:
        return {'code': 0, 'result': None, 'msg': '没有图片'}
    # 获取ocrType。1：ocr，2：点选，3：滑块。
    if 'ocrType' in data:
        ocrType = data['ocrType']
    else:
        ocrType = 1
    # 获取comp参数，digit-纯数字、alpha-纯字母、alnum-数字和字母
    if 'comp' in data:
        comp = data['comp']
        if comp not in ['digit', 'alpha', 'alnum']:
            comp = 'alnum'
    else:
        comp = 'alnum'
    # 获取lenth参数
    if 'lenth' in data:
        lenth = data['lenth']
        if not lenth.isdigit():
            lenth = 0
        else:
            lenth = int(lenth)
    else:
        lenth = 0
    try:
        if ocrType == 1:
            result = handleOcr(imgdata, comp, lenth)
        elif ocrType == 2:
            result = handleDet(imgdata)
        elif ocrType == 3:
            result = handleSlide(imgdata, backgroundImgdata)
        else:
            return {'code': 0, 'result': None, 'msg': '失败'}
        if not 'urlList' in data or cookies == {}:
            return {'code': 1, 'result': result, 'msg': 'success'}
        else:
            return {'code': 1, 'cookies': cookies, 'result': result, 'msg': 'success'}
    except Exception as e:
        return {'code': 0, 'result': None, 'msg': str(e).strip()}

# img 处理
@PythonT4.post("/rebuildimg")
def rebuildImg(data: dict = Body(...)):
    cookies = {}
    if 'header' in data:
        header = data['header']
    else:
        header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.54 Safari/537.36'
        }
    if 'imgUrl' in data:
        url = data['imgUrl']
        try:
            r = requests.get(url, headers=header, timeout=30)
            for key, value in r.cookies.items():
                cookies.update({key: value})
            imgData = r.content
        except:
            return {'code': 0, 'result': None, 'msg': '访问{}超时'.format(url)}
    elif 'imgData' in data:
        imgData = data['imgData']
        if imgData.startswith('data'):
            imgData = imgData.split(',', 1)[1]
        imgData = b64decode(imgData)
    else:
        return {'code': 0, 'result': None, 'msg': '没有图片'}
    if 'offsetsDict' in data:
        offsetsDict = data['offsetsDict']
    else:
        return {'code': 0, 'result': None, 'msg': '缺少offsetsList参数'}
    if 'whList' in data:
        whList = data['whList']
    else:
        return {'code': 0, 'result': None, 'msg': 'whList'}
    try:
        weight, height = whList
        imgStream = BytesIO(imgData)
        imgFile = Image.open(imgStream)
        newimgFile = Image.new('RGB', (260, 116))
        if 'upper' in offsetsDict:
            i = 0
            for offset in offsetsDict['upper']:
                offset = (int(offset[0]), int(offset[1]), int(offset[0]) + int(weight), int(offset[1]) + int(height))
                newoffset = (0 + i, 0)
                i += int(weight)
                region = imgFile.crop(offset)
                newimgFile.paste(region, newoffset)
        if 'lower' in offsetsDict:
            i = 0
            for offset in offsetsDict['lower']:
                offset = (int(offset[0]), int(offset[1]), int(offset[0]) + int(weight), int(offset[1]) + int(height))
                newoffset = (0 + i, int(height))
                i += int(weight)
                region = imgFile.crop(offset)
                newimgFile.paste(region, newoffset)
        imgFile = BytesIO()
        newimgFile.save(imgFile, format="PNG")
        imgData = b64encode(imgFile.getvalue()).decode()
        if not 'imgUrl' in data or cookies == {}:
            return {'code': 1, 'result': imgData, 'msg': 'success'}
        else:
            return {'code': 1, 'cookies': cookies, 'result': imgData, 'msg': 'success'}
    except Exception as e:
        return {'code': 0, 'result': None, 'msg': str(e).strip()}

# 以8000端口启动服务
uvicorn.run(PythonT4, host="0.0.0.0", port=8000, reload=False)