"""scripts 測試共用設定：讓測試可直接 import version_data / telegram_hook。

scripts/ 為獨立 script 目錄（非套件），故於收集階段把 scripts/ 加入 sys.path，
測試模組即可 `import version_data` 與 `import telegram_hook`。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
