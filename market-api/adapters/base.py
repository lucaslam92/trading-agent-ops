from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RawSnapshot:
    """Adapter 返回的原始数据，不含滑窗历史"""
    indices: list[dict]
    sectors: list[dict]
    leaders: list[dict]
    globals: list[dict]
    breadth: dict
    source: str


class DataAdapter(ABC):
    @abstractmethod
    async def fetch(self) -> RawSnapshot: ...
