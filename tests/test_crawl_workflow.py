"""CI/CD 基建結構測試：.github/workflows/crawl.yml（功能 002 §1.2-§1.4）。

以 PyYAML 解析工作流並斷言觸發/並發/權限/job 結構，對應 BDD 12 scenarios：
- @happy-path @daily：cron '0 6 * * *' 排程觸發
- @happy-path @manual-trigger：workflow_dispatch 手動觸發
- @edge-case @robustness：concurrency group + cancel-in-progress: false
- @error-handling：crawl/deploy 雙 job 切分（needs: crawl）、per-job 最小權限
- @business-rule：commit step if 條件（無異動跳過 commit）
- @integration @placeholder：telegram step continue-on-error: true

注意：PyYAML 1.1 會把 `on:` 解析成 boolean True key，需以 doc[True] 存取觸發區段。
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "crawl.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    assert WORKFLOW_PATH.exists(), f"缺少工作流檔：{WORKFLOW_PATH}"
    with WORKFLOW_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _on_section(doc: dict) -> dict:
    """PyYAML 1.1 將 `on:` 解析為 boolean True key；兩者皆相容處理。"""
    for key, value in doc.items():
        if key is True or key == "on":
            return value
    raise AssertionError("crawl.yml 缺少 on 觸發區段（PyYAML 將 `on:` 解析為 True key）")


def test_triggers_schedule_and_manual(workflow: dict) -> None:
    """BDD @happy-path @daily / @manual-trigger：cron + workflow_dispatch 雙觸發。"""
    on = _on_section(workflow)
    crons = [item["cron"] for item in on["schedule"]]
    assert crons == ["0 6 * * *"], f"schedule cron 應為 '0 6 * * *'，實際：{crons}"
    assert "workflow_dispatch" in on, "缺少 workflow_dispatch 手動觸發"


def test_concurrency_serialize(workflow: dict) -> None:
    """BDD @edge-case @robustness：並發觸發時序列化，不取消進行中的 run。"""
    concurrency = workflow["concurrency"]
    assert concurrency["group"] == "pages-deploy"
    assert concurrency["cancel-in-progress"] is False


def test_top_level_permissions_empty(workflow: dict) -> None:
    """§1.3 權限最小化：頂層 permissions 為空，各 job 自行宣告。"""
    assert workflow["permissions"] == {}


def test_jobs_and_needs(workflow: dict) -> None:
    """BDD @error-handling：crawl 失敗 → deploy 因 needs 不啟動。"""
    assert set(workflow["jobs"].keys()) == {"crawl", "deploy"}
    needs = workflow["jobs"]["deploy"]["needs"]
    needs_list = needs if isinstance(needs, list) else [needs]
    assert needs_list == ["crawl"]


def test_checkouts_pin_default_branch(workflow: dict) -> None:
    """§1.4 Checkout：crawl/deploy 皆需顯式 ref 到 default_branch。

    預設 actions/checkout 對 schedule / workflow_dispatch 事件會 checkout
    觸發時點的 GITHUB_SHA；crawl job 於 run 中途 push 資料 commit 後，
    deploy job 若以預設 checkout 會取到舊 SHA（build 到舊版資料，違反
    §1.4「取回含最新資料 commit 的程式碼」）；顯式 ref 才會取 job 執行當下
    的 main tip（並涵蓋 BDD @edge-case @robustness 並發場景的資料基準）。"""
    expected = "${{ github.event.repository.default_branch }}"
    for job in ("crawl", "deploy"):
        steps = workflow["jobs"][job]["steps"]
        checkout_steps = [s for s in steps if "actions/checkout" in s.get("uses", "")]
        assert checkout_steps, f"{job} job 缺少 actions/checkout step"
        with_ = checkout_steps[0].get("with") or {}
        assert with_.get("ref") == expected, (
            f"{job} job 的 checkout 應固定 ref={expected}（預設 checkout 取觸發時點 GITHUB_SHA）"
        )


def test_crawl_job_permissions_minimal(workflow: dict) -> None:
    """§1.3 權限最小化：crawl 僅 contents: write，不含 pages/id-token。"""
    perms = workflow["jobs"]["crawl"]["permissions"]
    assert perms == {"contents": "write"}
    assert "pages" not in perms
    assert "id-token" not in perms


def test_crawl_job_steps(workflow: dict) -> None:
    """crawl job steps：version step / telegram continue-on-error / commit if 條件。"""
    steps = workflow["jobs"]["crawl"]["steps"]
    by_id = {s.get("id"): s for s in steps if s.get("id")}

    # step id: version → 執行 version_data.py（BDD @business-rule @cache-busting）
    assert "version" in by_id, "缺少 id=version 的 step"
    assert "version_data.py" in by_id["version"]["run"]

    # telegram hook：continue-on-error: true（BDD @integration @placeholder）
    telegram_steps = [s for s in steps if "telegram_hook.py" in s.get("run", "")]
    assert telegram_steps, "缺少 telegram_hook step"
    assert telegram_steps[0].get("continue-on-error") is True

    # commit step：if changed + bot 身分 + git add data/ + pull --rebase + push
    commit_steps = [s for s in steps if s.get("if")]
    assert commit_steps, "缺少條件執行的 commit step"
    commit = commit_steps[0]
    assert "steps.version.outputs.changed == 'true'" in commit["if"]
    run = commit["run"]
    assert "git add data/" in run
    assert "coolpc-tracker[bot]" in run  # bot 身分 name/email（§9.3）
    assert "git pull --rebase" in run
    assert "git push" in run
    assert commit.get("env", {}).get("GH_TOKEN") == "${{ github.token }}"

    # 順序：telegram（continue-on-error）必須在 commit 之前（006 契約）
    index_telegram = steps.index(telegram_steps[0])
    index_commit = steps.index(commit)
    assert index_telegram < index_commit


def test_deploy_job_permissions_minimal(workflow: dict) -> None:
    """§1.3 權限最小化：deploy 僅 pages + id-token write。"""
    perms = workflow["jobs"]["deploy"]["permissions"]
    assert perms == {"pages": "write", "id-token": "write"}


def test_deploy_job_environment(workflow: dict) -> None:
    """deploy environment：github-pages + page_url。"""
    env = workflow["jobs"]["deploy"]["environment"]
    assert env["name"] == "github-pages"
    assert "steps.deployment.outputs.page_url" in env["url"]


def test_deploy_job_steps(workflow: dict) -> None:
    """deploy steps：build（BASE_PATH 注入）+ configure/upload/deploy-pages。"""
    deploy = workflow["jobs"]["deploy"]
    steps = deploy["steps"]
    uses = " ".join(s.get("uses", "") for s in steps)
    assert "actions/configure-pages@v5" in uses
    assert "actions/upload-pages-artifact@v3" in uses
    assert "actions/deploy-pages@v4" in uses

    build_steps = [s for s in steps if "npm run build" in s.get("run", "")]
    assert build_steps, "缺少 Install & build step"
    build = build_steps[0]
    assert build["env"]["BASE_PATH"] == "/${{ github.event.repository.name }}/"
    assert "npm ci" in build["run"]
