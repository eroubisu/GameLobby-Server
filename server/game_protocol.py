"""
服务端游戏协议定义

定义游戏引擎和房间必须实现的标准接口，使 chat_server 和 lobby_engine
无需知道具体游戏类型即可统一操作。

扩展方式：
  1. 在 games/xxx/ 下实现 Engine 和 Room，满足本模块定义的接口
  2. 在 GAME_INFO 中声明 locations / has_bot / has_rooms
  3. 框架自动发现并注册
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── 游戏事件 ──

@dataclass
class GameEvent:
    """
    游戏引擎产生的事件 — 统一的"输出协议"

    chat_server 不需要知道具体游戏逻辑，只负责将事件序列化并分发。
    """
    type: str          # room_update / hand_update / game_message /
                       # action_prompt / self_action_prompt /
                       # win_animation / game_end / location_update
    data: dict = field(default_factory=dict)
    target: str = ""   # 空=广播房间, 玩家名=点对点


# ── GAME_INFO 扩展字段 ──

# 每个游戏模块的 GAME_INFO 应包含以下字段：
#
# GAME_INFO = {
#     'id': 'mahjong',
#     'name': '麻将',
#     'description': '...',
#     'min_players': 4,
#     'max_players': 4,
#     'icon': '🀄',
#
#     # ── 以下为框架扩展字段 ──
#     'has_rooms': True,         # 是否有房间系统（JRPG 为 False）
#     'has_bot': True,           # 是否支持机器人
#     'locations': {             # 自动注入 LOCATION_HIERARCHY
#         'mahjong': ('麻将', 'lobby'),
#         'mahjong_room': ('房间', 'mahjong'),
#         'mahjong_playing': ('对局中', 'mahjong_room'),
#     },
# }
