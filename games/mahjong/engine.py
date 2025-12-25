"""
麻将游戏引擎 - 房间管理
"""

import time
from .room import MahjongRoom


class MahjongEngine:
    """麻将游戏引擎 - 管理所有房间"""
    
    def __init__(self, game_data):
        self.game_data = game_data
        self.rooms = {}  # {room_id: MahjongRoom}
        self.player_rooms = {}  # {player_name: room_id} 玩家所在房间
        self.invites = {}  # {target_name: {'from': host, 'room_id': room_id, 'time': timestamp}}
    
    def create_room(self, host_name, game_mode='hanchan', match_type='yuujin'):
        """创建房间
        
        Args:
            host_name: 房主名称
            game_mode: 游戏模式 'tonpu'=东风战, 'hanchan'=半庄战
            match_type: 段位场类型 'yuujin'=友人场, 'dou'=铜之间, etc.
            
        Returns:
            (room, error): 房间对象和错误信息
        """
        if host_name in self.player_rooms:
            return None, "你已经在一个房间中了"
        
        room_id = f"room_{len(self.rooms) + 1}_{int(time.time()) % 10000}"
        room = MahjongRoom(room_id, host_name, game_mode=game_mode, match_type=match_type)
        self.rooms[room_id] = room
        self.player_rooms[host_name] = room_id
        return room, None
    
    def get_room(self, room_id):
        """获取房间"""
        return self.rooms.get(room_id)
    
    def get_player_room(self, player_name):
        """获取玩家所在房间"""
        room_id = self.player_rooms.get(player_name)
        if room_id:
            return self.rooms.get(room_id)
        return None
    
    def join_room(self, room_id, player_name):
        """加入房间"""
        if player_name in self.player_rooms:
            return None, "你已经在一个房间中了"
        
        room = self.rooms.get(room_id)
        if not room:
            return None, "房间不存在"
        if room.is_full():
            return None, "房间已满"
        if room.state != 'waiting':
            return None, "游戏已开始，无法加入"
        
        pos = room.add_player(player_name)
        if pos >= 0:
            self.player_rooms[player_name] = room_id
            return room, None
        return None, "加入失败"
    
    def leave_room(self, player_name):
        """离开房间"""
        room_id = self.player_rooms.get(player_name)
        if not room_id:
            return None, "你不在任何房间中"
        
        room = self.rooms.get(room_id)
        if room:
            room.remove_player(player_name)
            del self.player_rooms[player_name]
            
            # 房间空了就删除
            if room.get_player_count() == 0:
                del self.rooms[room_id]
                return None, "已离开房间（房间已解散）"
            
            # 转移房主
            if room.host == player_name:
                for i in range(4):
                    if room.players[i]:
                        room.host = room.players[i]
                        break
            
            return room, None
        
        del self.player_rooms[player_name]
        return None, "已离开房间"
    
    def remove_room(self, room_id):
        """删除房间"""
        if room_id in self.rooms:
            room = self.rooms[room_id]
            for player in room.players.values():
                if player and player in self.player_rooms:
                    del self.player_rooms[player]
            del self.rooms[room_id]
    
    def list_rooms(self):
        """列出所有等待中的房间"""
        waiting_rooms = []
        for room_id, room in self.rooms.items():
            if room.state == 'waiting':
                waiting_rooms.append(room.get_status())
        return waiting_rooms
    
    # ==================== 邀请系统 ====================
    
    def send_invite(self, from_name, to_name, room_id):
        """发送邀请"""
        self.invites[to_name] = {
            'from': from_name,
            'room_id': room_id,
            'time': time.time()
        }
    
    def get_invite(self, player_name):
        """获取玩家收到的邀请（5分钟过期）"""
        invite = self.invites.get(player_name)
        if invite:
            if time.time() - invite['time'] < 300:
                return invite
            else:
                del self.invites[player_name]
        return None
    
    def clear_invite(self, player_name):
        """清除邀请"""
        if player_name in self.invites:
            del self.invites[player_name]
