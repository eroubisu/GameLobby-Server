"""
游戏引擎标准接口协议

所有游戏引擎应实现此协议，使大厅能够统一管理命令路由、断线处理、导航等功能。

两种引擎类型(通过 GAME_INFO['per_player'] 区分):
- 房间制引擎(per_player=False): 共享实例，管理多个房间 (如 chess, mahjong)
- 玩家制引擎(per_player=True): 每个玩家独立实例 (如 jrpg)
"""

from typing import Protocol, runtime_checkable, Any


@runtime_checkable
class GameEngine(Protocol):
    """游戏引擎标准接口"""

    def handle_command(self, lobby: Any, player_name: str, player_data: dict,
                       cmd: str, args: str) -> Any:
        """处理游戏指令（包括游戏内待确认状态）

        Returns: 响应消息(str/dict)，None 表示未匹配
        """
        ...

    def handle_disconnect(self, lobby: Any, player_name: str) -> list[dict]:
        """处理玩家断线

        Returns: 需要发送的通知列表 [{'target': str, 'message': str, ...}]
        """
        ...

    def handle_back(self, lobby: Any, player_name: str, player_data: dict) -> Any:
        """处理 /back 指令

        引擎根据玩家当前位置决定行为:
        - 对局中: 弹出确认提示
        - 房间中: 离开房间
        - 游戏根位置: 返回大厅
        """
        ...

    def handle_quit(self, lobby: Any, player_name: str, player_data: dict) -> Any:
        """处理 /quit 或 /home 指令"""
        ...

    def get_welcome_message(self, player_data: dict) -> dict:
        """获取进入游戏时的欢迎信息

        Returns: {'action': 'location_update', 'message': str, ...}
        """
        ...

    def get_player_room_data(self, player_name: str) -> dict | None:
        """获取玩家所在房间的数据（用于UI更新）

        Returns: 房间数据dict，不在房间则返回 None
        """
        ...
