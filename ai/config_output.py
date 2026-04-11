"""
ai/config_output.py

将 AI 决策结果写入 configs/strategy_runtime.json，
CTA 策略在 on_bar 中读取该文件以更新参数。

职责：
- 增加 version 版本号（策略侧通过版本号判断是否需要刷新参数）
- 写入时加文件锁，避免策略侧并发读取产生脏数据
- 记录写入日志
"""

import json
import logging
import os
import fcntl
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

_DEFAULT_RUNTIME_PATH = Path(__file__).parent.parent / "configs" / "strategy_runtime.json"


class ConfigOutput:
    """
    将 ParameterProvider 输出的配置 dict 持久化到 JSON 文件。

    调用方式：
        output = ConfigOutput()
        output.write(config_dict)
    """

    def __init__(self, runtime_path: Path = _DEFAULT_RUNTIME_PATH) -> None:
        self.runtime_path = runtime_path
        self._version = self._load_current_version()

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def write(self, config: Dict[str, Any]) -> int:
        """
        写入最新配置，自动递增 version。

        Parameters
        ----------
        config : dict
            来自 ParameterProvider.get() 的配置字典。

        Returns
        -------
        int : 本次写入的 version 号
        """
        self._version += 1
        payload = {
            **config,
            "version": self._version,
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        self._write_atomic(payload)
        logger.info(
            "ConfigOutput: wrote version=%d regime=%s strategy=%s",
            self._version,
            config.get("regime"),
            config.get("strategy"),
        )
        return self._version

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _load_current_version(self) -> int:
        """读取已有文件的 version，用于续号。"""
        if self.runtime_path.exists():
            try:
                with open(self.runtime_path) as f:
                    data = json.load(f)
                return int(data.get("version", 0))
            except (json.JSONDecodeError, KeyError, ValueError):
                pass
        return 0

    def _write_atomic(self, payload: Dict[str, Any]) -> None:
        """使用文件锁保证写入原子性（同一进程内适用）。"""
        tmp_path = self.runtime_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        os.replace(tmp_path, self.runtime_path)
