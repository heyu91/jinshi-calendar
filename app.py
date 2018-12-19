# coding: utf-8

import time
import json
import yaml
import aiohttp
import asyncio
import async_timeout
from urllib import parse
from itertools import chain
from ics import Calendar, Event

from flask import Flask, request
from flask import render_template
from flask_sockets import Sockets


loop = asyncio.get_event_loop()
app = Flask(__name__)
sockets = Sockets(app)


ONEWEEK = 86400 * 7


async def fetch(url, params=None):
    # Aiohttp使用ClientSession作为主要的接口发起请求
    # Session(会话)在使用完毕之后需要关闭，
    # 关闭Session是另一个异步操作，
    # 所以每次你都需要使用async with关键字，
    # with语句可以保证在处理session的时候，
    # 总是能正确的关闭它。
    async with aiohttp.ClientSession() as session, async_timeout.timeout(5):
        async with session.get(url, params=params) as response:
            response = await response.read()
            print("    GOT {url}?{params}".format(url=url, params=parse.urlencode(params)))
            return response


async def get_cal(start, end):
    url = "https://api-prod.wallstreetcn.com/apiv1/finfo/calendars"
    tasks = list()
    for start_ in range(start, end, ONEWEEK):
        end_ = min(start_ + ONEWEEK, end)
        task = fetch(url, params=dict(start=start_, end=end_))
        tasks.append(task)
    responses = await asyncio.gather(*tasks)
    # you now have all response bodies in this variable

    def loads(content):
        try:
            return json.loads(content)['data']['items']
        except Exception:
            return list()

    return chain(*map(loads, responses))


def get_ics(start=None, end=None):
    if start is not None:
        start = int(time.mktime(time.strptime(start, '%Y%m%d')))
    if end is not None:
        end = int(time.mktime(time.strptime(end, '%Y%m%d')))

    if start is None and end is None:
        start = int(time.time()) - ONEWEEK * 4
        end = int(time.time()) + ONEWEEK * 12
    else:
        start = start or end - ONEWEEK * 8
        end = end or start + ONEWEEK * 8

    def format_title(event):
        return "[{star:<3s}{country:s}]{title:s}".format(
            star='★' * event.get('stars', 0),
            country=event.get('country', ''),
            title=event.get('title', ''),
        )

    def format_desc(event):
        tamplete = """{desc}\n-----\n{detail}\n"""
        return tamplete.format(
            desc=event.get('description', ''),
            detail=yaml.dump(event, allow_unicode=True, default_flow_style=False),
        )

    events = loop.run_until_complete(get_cal(start, end))

    c = Calendar(creator='h.y@live.cn\nX-PUBLISHED-TTL:PT1H\nNAME:Wallstreetcn - Calendar\nDSCRIPTION:华尔街见闻日历')  # 设置建议1小时一更新

    def add_event(event):
        e = Event()
        e.uid = str(event.get('id'))
        e.name = format_title(event)
        e.begin = event.get('timestamp', time.time())
        e.end = event.get('timestamp', time.time())
        e.description = format_desc(event)
        e.location = event.get('country', '')

        c.events.add(e)

    list(map(add_event, events))

    return c


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/calendar.ics', methods=['post', 'get'])
def calendar():
    start = request.args.get('start', None)
    end = request.args.get('end', None)
    print("GET /calendar.ics?start={start}&end={end}".format(start=start, end=end))
    return str(get_ics(start=start, end=end))
