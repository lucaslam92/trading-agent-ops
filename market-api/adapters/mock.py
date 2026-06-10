import random
from .base import DataAdapter, RawSnapshot


def _rnd(a, b):
    return a + random.random() * (b - a)


def _clamp(v, a, b):
    return min(b, max(a, v))


def _r(v, d=2):
    return round(v, d)


_SECTOR_SEED = [
    {'name': '光模块',   'changePct': 4.8,  'netInflow': 41.2,  'theme': 'AI算力'},
    {'name': '算力租赁', 'changePct': 3.9,  'netInflow': 28.6,  'theme': 'AI算力'},
    {'name': '通信设备', 'changePct': 3.1,  'netInflow': 33.4,  'theme': 'AI算力'},
    {'name': '半导体',   'changePct': 2.4,  'netInflow': 24.1,  'theme': '科技'},
    {'name': 'CPO',      'changePct': 5.6,  'netInflow': 19.8,  'theme': 'AI算力'},
    {'name': '消费电子', 'changePct': 1.6,  'netInflow':  9.2,  'theme': '科技'},
    {'name': '软件开发', 'changePct': 1.9,  'netInflow': 12.7,  'theme': '科技'},
    {'name': '机器人',   'changePct': 0.4,  'netInflow': -6.3,  'theme': '题材'},
    {'name': '电池',     'changePct': 0.9,  'netInflow':  4.1,  'theme': '新能源'},
    {'name': '光伏',     'changePct': -0.7, 'netInflow': -8.4,  'theme': '新能源'},
    {'name': '军工',     'changePct': 1.2,  'netInflow':  3.3,  'theme': '题材'},
    {'name': '医药商业', 'changePct': -0.3, 'netInflow': -2.1,  'theme': '医药'},
    {'name': '白酒',     'changePct': -1.4, 'netInflow': -15.6, 'theme': '消费'},
    {'name': '证券',     'changePct': 0.6,  'netInflow':  5.5,  'theme': '金融'},
    {'name': '银行',     'changePct': -0.5, 'netInflow': -11.2, 'theme': '红利'},
    {'name': '电力',     'changePct': -0.9, 'netInflow': -7.8,  'theme': '红利'},
    {'name': '煤炭',     'changePct': -1.1, 'netInflow': -9.1,  'theme': '红利'},
    {'name': '房地产',   'changePct': -1.8, 'netInflow': -5.4,  'theme': '周期'},
]

_LEADER_SEED = [
    {'code': '300308', 'name': '中际旭创', 'sector': '光模块',   'price': 168.4, 'changePct': 6.2,  'volRatio': 1.4, 'theme': 'AI算力'},
    {'code': '300394', 'name': '天孚通信', 'sector': '光模块',   'price': 92.7,  'changePct': 5.1,  'volRatio': 1.3, 'theme': 'AI算力'},
    {'code': '601138', 'name': '工业富联', 'sector': '算力租赁', 'price': 31.2,  'changePct': 4.4,  'volRatio': 1.2, 'theme': 'AI算力'},
    {'code': '002371', 'name': '北方华创', 'sector': '半导体',   'price': 412.5, 'changePct': 2.1,  'volRatio': 0.9, 'theme': '科技'},
    {'code': '688981', 'name': '中芯国际', 'sector': '半导体',   'price': 58.9,  'changePct': 1.7,  'volRatio': 1.1, 'theme': '科技'},
    {'code': '603728', 'name': '鸣志电器', 'sector': '机器人',   'price': 44.6,  'changePct': -3.2, 'volRatio': 2.1, 'theme': '题材'},
    {'code': '688017', 'name': '绿的谐波', 'sector': '机器人',   'price': 96.1,  'changePct': -1.8, 'volRatio': 1.6, 'theme': '题材'},
    {'code': '600900', 'name': '长江电力', 'sector': '电力',     'price': 28.3,  'changePct': -0.6, 'volRatio': 0.7, 'theme': '红利'},
    {'code': '601088', 'name': '中国神华', 'sector': '煤炭',     'price': 39.8,  'changePct': -1.0, 'volRatio': 0.8, 'theme': '红利'},
    {'code': '601398', 'name': '工商银行', 'sector': '银行',     'price': 6.42,  'changePct': -0.4, 'volRatio': 0.6, 'theme': '红利'},
]

_INDEX_SEED = [
    {'code': 'SH000001', 'label': '上证指数', 'price': 3284.6,  'changePct': 0.82},
    {'code': 'SZ399001', 'label': '深证成指', 'price': 10512.3, 'changePct': 1.14},
    {'code': 'SZ399006', 'label': '创业板指', 'price': 2118.7,  'changePct': 1.63},
    {'code': 'SH000688', 'label': '科创50',   'price': 1042.9,  'changePct': 2.21},
    {'code': 'SZ399330', 'label': '深证100',  'price': 6201.4,  'changePct': 1.05},
]

_GLOBAL_SEED = [
    {'code': 'NDX',    'label': '纳斯达克', 'changePct': 0.54,  'note': '收盘'},
    {'code': 'HSTECH', 'label': '恒生科技', 'changePct': 0.81,  'note': '收盘'},
    {'code': 'CN00Y',  'label': 'A50期指',  'changePct': 0.23,  'note': '实时'},
    {'code': 'US10Y',  'label': '美10年债', 'changePct': 4.30,  'note': '收益率', 'isLevel': True},
    {'code': 'GC',     'label': '黄金',     'changePct': 0.12,  'note': '隔夜'},
    {'code': 'CL',     'label': '原油',     'changePct': -0.34, 'note': '隔夜'},
    {'code': 'NVDA',   'label': 'NVDA盘后', 'changePct': 1.21,  'note': '盘后'},
]

_INDEX_WEIGHTS = [0.7, 0.85, 1.25, 1.5, 0.95]


class MockAdapter(DataAdapter):
    def __init__(self):
        self._sectors = [dict(s) for s in _SECTOR_SEED]
        self._leaders = [
            {**l, 'open': _r(l['price'] / (1 + l['changePct'] / 100))}
            for l in _LEADER_SEED
        ]
        self._indices = [
            {**idx, 'prevClose': _r(idx['price'] / (1 + idx['changePct'] / 100))}
            for idx in _INDEX_SEED
        ]
        self._globals = [dict(g) for g in _GLOBAL_SEED]
        self._breadth = {'up': 3142, 'down': 1684, 'flat': 220, 'limitUp': 58, 'limitDown': 4}

    def _tick(self):
        theme_drift: dict[str, float] = {}
        for s in self._sectors:
            if s['theme'] not in theme_drift:
                theme_drift[s['theme']] = _rnd(-0.18, 0.18)

        for s in self._sectors:
            drift = theme_drift[s['theme']] + _rnd(-0.22, 0.22)
            s['changePct'] = _r(_clamp(s['changePct'] + drift, -6, 8))
            s['netInflow'] = _r(_clamp(s['netInflow'] + drift * 3 + _rnd(-1.2, 1.2), -40, 60), 1)

        for l in self._leaders:
            sec = next((s for s in self._sectors if s['name'] == l['sector']), None)
            pull = (sec['changePct'] - l['changePct']) * 0.15 if sec else 0
            l['changePct'] = _r(_clamp(l['changePct'] + pull + _rnd(-0.35, 0.35), -10, 12))
            l['price'] = _r(l['open'] * (1 + l['changePct'] / 100), 2)
            l['volRatio'] = _r(_clamp(l['volRatio'] + _rnd(-0.05, 0.05), 0.3, 3), 2)

        avg = sum(s['changePct'] for s in self._sectors) / len(self._sectors)
        for idx, w in zip(self._indices, _INDEX_WEIGHTS):
            idx['changePct'] = _r(_clamp(avg * w + _rnd(-0.15, 0.15), -5, 6))
            idx['price'] = _r(idx['prevClose'] * (1 + idx['changePct'] / 100), 2)

        b = self._breadth
        b['up'] = int(_clamp(b['up'] + _rnd(-60, 60) + avg * 30, 200, 5000))
        b['down'] = int(_clamp(5046 - b['up'] - b['flat'], 0, 5000))
        b['limitUp'] = int(_clamp(b['limitUp'] + _rnd(-3, 3) + avg * 2, 0, 200))
        b['limitDown'] = int(_clamp(b['limitDown'] + _rnd(-1, 1) - avg, 0, 100))

    async def fetch(self) -> RawSnapshot:
        self._tick()
        return RawSnapshot(
            indices=[
                {'code': x['code'], 'label': x['label'], 'price': x['price'],
                 'changePct': x['changePct'], 'prevClose': x['prevClose']}
                for x in self._indices
            ],
            sectors=[
                {'name': s['name'], 'changePct': s['changePct'],
                 'netInflow': s['netInflow'], 'theme': s['theme']}
                for s in self._sectors
            ],
            leaders=[
                {'code': l['code'], 'name': l['name'], 'sector': l['sector'],
                 'price': l['price'], 'changePct': l['changePct'],
                 'open': l['open'], 'volRatio': l['volRatio'], 'theme': l['theme']}
                for l in self._leaders
            ],
            globals=[dict(g) for g in self._globals],
            breadth=dict(self._breadth),
            source='mock',
        )
