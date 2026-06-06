import asyncio
import time
from collections import deque

from adapters.base import DataAdapter
from sse_manager import SSEManager


class Scheduler:
    def __init__(self, adapter: DataAdapter, sse_manager: SSEManager, interval: float = 2.2):
        self.adapter = adapter
        self.sse = sse_manager
        self.interval = interval
        self._sector_hist:  dict[str, deque] = {}
        self._sector_flow:  dict[str, deque] = {}
        self._leader_spark: dict[str, deque] = {}

    async def run(self):
        while True:
            try:
                raw = await self.adapter.fetch()
                snapshot = self._build_snapshot(raw)
                self.sse.broadcast(snapshot)
            except Exception as e:
                print(f"[Scheduler] fetch error: {e}")
            await asyncio.sleep(self.interval)

    def _build_snapshot(self, raw) -> dict:
        for s in raw.sectors:
            self._sector_hist.setdefault(s['name'], deque(maxlen=40)).append(s['changePct'])
            self._sector_flow.setdefault(s['name'], deque(maxlen=40)).append(s['netInflow'])
        for l in raw.leaders:
            self._leader_spark.setdefault(l['code'], deque(maxlen=30)).append(l['changePct'])

        sectors = [
            {**s,
             'hist':     list(self._sector_hist.get(s['name'], [])),
             'flowHist': list(self._sector_flow.get(s['name'], []))}
            for s in raw.sectors
        ]
        leaders = [
            {**l, 'spark': list(self._leader_spark.get(l['code'], []))}
            for l in raw.leaders
        ]

        return {
            'indices':   raw.indices,
            'sectors':   sectors,
            'leaders':   leaders,
            'globals':   raw.globals,
            'breadth':   raw.breadth,
            'source':    raw.source,
            'updatedAt': int(time.time() * 1000),
        }
