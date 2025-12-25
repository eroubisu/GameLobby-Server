"""
麻将游戏模块

模块结构:
- engine.py: 游戏引擎 (MahjongEngine - 房间管理)
- room.py: 房间类 (MahjongRoom - 组合各模块)
- tenpai.py: 听牌分析 (TenpaiMixin)
- actions.py: 吃碰杠胡操作 (ActionsMixin)
- scoring.py: 结算计分 (ScoringMixin)
- game_data.py: 牌数据定义和工具函数
- yaku.py: 役种判定
- bot_ai.py: 机器人 AI

旧模块 game_engine.py 仍保留用于向后兼容
"""

# 新的模块化导入
from .engine import MahjongEngine
from .room import MahjongRoom
from .tenpai import TenpaiMixin
from .actions import ActionsMixin
from .scoring import ScoringMixin
from .game_data import MahjongData
from .bot_ai import BotAI, get_bot_discard, get_bot_action, get_bot_self_action

# 游戏信息
GAME_INFO = {
    'id': 'mahjong',
    'name': '麻将',
    'description': '四人麻将游戏',
    'min_players': 4,
    'max_players': 4,
    'icon': '🀄'
}
