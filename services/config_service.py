"""
services/config_service.py

配置文件读取服务。

提供对 configs/ 目录下所有 JSON 配置文件的统一读写接口，
并持有对 strategy_runtime.json 的监控能力（版本检查）。
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_CONFIGS_DIR = Path(__file__).parent.parent / "configs"


class ConfigService:
    """
    配置服务。

    调用方式：
        svc = ConfigService()
        cfg = svc.load("backtest_config")   # 加载 configs/backtest_config.json
        svc.save("strategy_runtime", data)  # 写入 configs/strategy_runtime.json
    """

    def __init__(self, configs_dir: Path = _CONFIGS_DIR) -> None:
        self._dir = configs_dir
        self._cache: Dict[str, Dict[str, Any]] = {}

    def load(self, name: str) -> Dict[str, Any]:
        """
        读取 configs/<name>.json。

        Parameters
        ----------
        name : str
            配置文件名（不含 .json 后缀）。

        Returns
        -------
        dict : 配置内容
        """
        path = self._dir / f"{name}.json"
        if not path.exists():
            logger.warning("ConfigService.load: 文件不存在 %s", path)
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._cache[name] = data
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.error("ConfigService.load: 读取失败 %s - %s", path, e)
            return {}

    def save(self, name: str, data: Dict[str, Any]) -> None:
        """
        写入 configs/<name>.json（覆盖写）。

        Parameters
        ----------
        name : str
            配置文件名（不含 .json 后缀）。
        data : dict
            要写入的内容。
        """
        path = self._dir / f"{name}.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._cache[name] = data
        except OSError as e:
            logger.error("ConfigService.save: 写入失败 %s - %s", path, e)

    def get_runtime_version(self) -> int:
        """快速读取 strategy_runtime.json 的 version 字段，不做完整解析。"""
        path = self._dir / "strategy_runtime.json"
        if not path.exists():
            return -1
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return int(data.get("version", 0))
        except (json.JSONDecodeError, OSError, ValueError):
            return -1
