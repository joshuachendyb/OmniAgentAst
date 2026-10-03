# -*- coding: utf-8 -*-
"""守护：远端模型元数据「字段静默丢弃」与「DTO 契约漂移」 — 小欧 2026-10-03

由来：2026-09-29 与 2026-10-03 两次同类复发 —— AMD/OpenRouter 下发的字段被解析层静默丢弃，
  致前端靠 id.includes('-free') 猜免费（实测 460 个命中 0）。故立机制性守护：
  D1 键集闭锁（解析层输出键集 == DTO 声明，多/少都红；DTO 漂移会让整个端点 500）
  D2 free/stability 类型归一（脏类型不污染下游）
  D3 分层不变量：解析层只透传不判免费（免费归前端 isFreeModel）

编辑历史:
  2026-10-03 - 小欧 - 新建（D1/D2/D3）— 小欧 2026-10-03
"""
from typing import Any, Dict, List

import pytest

from app.api.v1.model_routes import RemoteModelItem
from app.services.model.model_service import _parse_remote_models_body


class _Resp:
    """最小 httpx.Response 替身：_parse_remote_models_body 只用 status_code 与 json()"""

    def __init__(self, payload: Any, status_code: int = 200):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


def _parse(payload: Any) -> List[Dict[str, Any]]:
    models, err = _parse_remote_models_body(_Resp(payload))
    assert err is None, f"解析不应失败, err={err}"
    assert models is not None
    return models


def _one(**over: Any) -> Dict[str, Any]:
    """单条远端模型，键可覆盖"""
    item: Dict[str, Any] = {"id": "m-1", "name": "M1"}
    item.update(over)
    return _parse({"data": [item]})[0]


# ---------------------------------------------------------------------------
# D1 键集闭锁
# ---------------------------------------------------------------------------

def test_d1_解析层键集与DTO声明完全一致():
    """解析层输出多一个键 → DTO 没声明 → response_model 校验失败 → 整个模型库端点 500。
    解析层少一个键 → 远端字段被静默丢弃（2026-10-03 复发的那类 bug）。故必须严格相等。"""
    parsed = _one()
    assert set(parsed.keys()) == set(RemoteModelItem.model_fields.keys()), (
        f"键集漂移。\n  解析层多出: "
        f"{set(parsed) - set(RemoteModelItem.model_fields)}\n"
        f"  解析层缺少: "
        f"{set(RemoteModelItem.model_fields) - set(parsed)}\n"
        f"  两侧需同步改 model_routes.RemoteModelItem 与 "
        f"model_service._parse_remote_models_body"
    )


def test_d1_多模型时键集恒一致_防按条目分支导致部分条目少字段():
    """解析层若有 if 分支只给部分条目补字段，单条用例查不出来 —— 故用异构两条一起断。"""
    models = _parse(
        {
            "data": [
                {"id": "with-all", "free": True, "stability": "stable"},
                {"id": "with-none"},
                {"id": "with-dirty", "free": "yes", "stability": 123},
            ]
        }
    )
    expected = set(RemoteModelItem.model_fields.keys())
    for m in models:
        assert set(m.keys()) == expected, f"{m['id']} 键集与其余条目不一致"


def test_d1_AMD实测形态可完整透传():
    """按 2026-10-03 AMD GET /models 实测响应裁一条，验证 free/stability 真的透传下来。"""
    m = _one(
        id="DeepSeek-V4-Flash",
        owned_by=None,  # AMD 不返回该字段
        context_length=1048576,
        pricing={"prompt": "0.00000014", "completion": "0.00000028"},
        supported_parameters=["temperature", "tools", "stream"],
        free=False,
        stability="experimental",
    )
    assert m["free"] is False
    assert m["stability"] == "experimental"
    assert m["context_length"] == 1048576
    assert m["owned_by"] is None, "AMD 不下发 owned_by，应为 None 而非报错"


# ---------------------------------------------------------------------------
# D2 free / stability 类型归一
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        (True, True),
        (False, False),
        ("true", None),   # 字符串不转 bool：前端用 `=== true` 严格判，脏值不冒充免费
        (1, None),       # int 不是 bool（isinstance(True, int) 为真，故必须用 bool 收）
        (0, None),
        (None, None),    # 缺键 → item.get 返回 None
    ],
)
def test_d2_free_类型归一(raw, expected):
    assert _one(free=raw)["free"] is expected


def test_d2_free_缺键时为None而非KeyError():
    """item.get 缺键返回 None；不得抛 KeyError（会让整个模型库端点 500）"""
    m = _parse({"data": [{"id": "m"}]})[0]
    assert m["free"] is None
    assert m["stability"] is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("experimental", "experimental"),
        ("stable", "stable"),
        ("", None),        # 空串 → None（下游避免显示空 Tag）
        ("   ", None),     # 纯空白 → None
        (123, None),       # 非字符串 → None
        (None, None),
    ],
)
def test_d2_stability_类型归一(raw, expected):
    assert _one(stability=raw)["stability"] == expected


def test_d2_stability_两侧空白保留原样():
    """只判空不 strip 落库值：远端原样透传，不擅自改写上游数据。"""
    assert _one(stability=" beta ")["stability"] == " beta "


# ---------------------------------------------------------------------------
# D3 分层不变量：解析层不判免费
# ---------------------------------------------------------------------------

def test_d3_解析层不掺入免费判定_free_false但pricing双0须原样透传():
    """AMD MinerU2.5-Pro 实测形态：free=false 而 pricing 全 0。
    解析层若擅自"修正"成 free=True，即为越权改写上游数据（判定权归前端 isFreeModel）。"""
    m = _one(
        id="MinerU2.5-Pro",
        free=False,
        pricing={"prompt": "0", "completion": "0"},
        context_length=0,
    )
    assert m["free"] is False, "解析层不得改写 free 字段"
    assert m["pricing"] == {"prompt": "0", "completion": "0"}, "pricing 须原样透传"


def test_d3_解析层不因名称带free尾巴而置位free字段():
    """名称尾巴是**前端**判据；后端不得据此把 free 置 True（会与 AMD 的记账语义打架）。"""
    m = _one(id="kimi-k2.5-free", free=None)
    assert m["free"] is None, "free 字段仅透传上游值，名称尾巴不参与后端判定"


# ---------------------------------------------------------------------------
# 既有行为不回归（本次改动不得破坏老口径）
# ---------------------------------------------------------------------------

def test_既有_裸数组结构仍兼容():
    assert _parse([{"id": "a"}, {"id": "b"}]) == [
        {"id": "a", "owned_by": None, "name": None, "description": None,
         "context_length": None, "pricing": {}, "architecture": {},
         "supported_parameters": [], "free": None, "stability": None},
        {"id": "b", "owned_by": None, "name": None, "description": None,
         "context_length": None, "pricing": {}, "architecture": {},
         "supported_parameters": [], "free": None, "stability": None},
    ]


def test_既有_id回退到model键():
    """部分 provider 只给 model 不给 id（item.get('id') or item.get('model') 双兜底）"""
    assert _parse({"data": [{"model": "legacy-model"}]})[0]["id"] == "legacy-model"


def test_既有_仍按id字母序排序():
    ids = [m["id"] for m in _parse({"data": [{"id": i} for i in ["zeta", "Alpha", "beta"]]})]
    assert ids == ["Alpha", "beta", "zeta"]


def test_既有_data非数组仍报错():
    models, err = _parse_remote_models_body(_Resp({"data": "not-a-list"}))
    assert models is None and err is not None