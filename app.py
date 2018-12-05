# coding: utf-8

import time
import json
import yaml
import requests
from itertools import chain
from ics import Calendar, Event

from flask import Flask, request
from flask import render_template
from flask_sockets import Sockets


app = Flask(__name__)
sockets = Sockets(app)


ONEWEEK = 86400 * 7


def get_cal(start, end):
    if end - start > ONEWEEK:
        return chain(*[get_cal(start_, start_ + ONEWEEK) for start_ in range(start, end, ONEWEEK)])
    else:
        try:
            return json.loads(
                requests.get(
                    "https://api-prod.wallstreetcn.com/apiv1/finfo/calendars",
                    params=dict(start=start, end=end)
                ).content
            )['data']['items']
        except Exception:
            return list()


def get_ics(start=None, end=None):
    if start is not None:
        start = int(time.mktime(time.strptime(start, '%Y%m%d')))
    if end is not None:
        end = int(time.mktime(time.strptime(end, '%Y%m%d')))

    if start is None and end is None:
        start = int(time.time()) - ONEWEEK * 4
        end = int(time.time()) + ONEWEEK * 8
    else:
        start = start or end - ONEWEEK * 4
        end = end or start + ONEWEEK * 4

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

    c = Calendar(creator='h.y@live.cn\nX-PUBLISHED-TTL:PT1H\nNAME:Wallstreetcn - Calendar\nDSCRIPTION:华尔街见闻日历')  # 设置建议1小时一更新
    for event in get_cal(start, end):

        e = Event()
        e.uid = str(event.get('id'))
        e.name = format_title(event)
        e.begin = event.get('timestamp', time.time())
        e.end = event.get('timestamp', time.time())
        e.description = format_desc(event)
        e.location = event.get('country', '')

        c.events.add(e)

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
