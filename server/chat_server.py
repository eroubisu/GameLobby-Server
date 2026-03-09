"""
聊天服务器
"""

import socket
import threading
import json
import os
import time
from datetime import datetime, timedelta, timezone

from .config import HOST, PORT, CHAT_LOG_DIR, CHAT_HISTORY_DIR, MAINTENANCE_HOUR
from .player_manager import PlayerManager
from .lobby_engine import LobbyEngine

# 导入游戏模块
from games.jrpg import JRPGData, JRPGEngine

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))


def get_beijing_now():
    """获取北京时间"""
    return datetime.now(BEIJING_TZ)


def get_today_date_str():
    """获取今天的日期字符串（以凌晨4点为分界）"""
    now = get_beijing_now()
    # 如果当前时间小于4点，属于前一天
    if now.hour < MAINTENANCE_HOUR:
        date = now.date() - timedelta(days=1)
    else:
        date = now.date()
    return date.strftime('%Y-%m-%d')


class ChatServer:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = {}
        self.lock = threading.Lock()
        
        # 游戏大厅引擎
        self.lobby_engine = LobbyEngine()
        # 设置邀请通知回调
        self.lobby_engine.set_invite_callback(self._send_invite_notification)
        
        # 机器人AI定时器
        self.bot_timers = {}  # {room_id: Timer}
        
        # 保留JRPG数据用于地图显示
        self.game_data = JRPGData()
        
        self.running = False
        self.chat_logs = {1: [], 2: []}  # 内存中的聊天记录
        self.current_date = get_today_date_str()  # 当前日期
        self.maintenance_thread = None
        self._load_chat_logs()
    
    def _get_mahjong_room(self, room_id):
        """获取麻将房间，不存在返回 None"""
        engine = self.lobby_engine.game_engines.get('mahjong')
        return engine.get_room(room_id) if engine else None

    def _for_each_room_player(self, room, callback, exclude_player=None):
        """遍历房间内的在线玩家，调用 callback(client, player_name, pos)"""
        with self.lock:
            for client, info in self.clients.items():
                player_name = info.get('name')
                if player_name and player_name != exclude_player:
                    pos = room.get_position(player_name)
                    if pos >= 0:
                        callback(client, player_name, pos)

    def _send_draw_notification(self, client, room, room_id, pos, player_name, drawn_tile):
        """发送摸牌通知（含自操作提示和立直自动摸切）"""
        msg = f"轮到你出牌！\n摸到: [{drawn_tile}]"
        self_actions = []
        if room.can_win(room.hands[pos][:-1], drawn_tile):
            self_actions.append("可以自摸 /tsumo")
        riichi_tiles = room.can_declare_riichi(pos)
        if riichi_tiles:
            self_actions.append("可以立直 /riichi <编号>")
        for k in (room.check_self_kong(pos) or []):
            cmd = 'ankan' if k['type'] == 'concealed' else 'kakan'
            label = '暗杠' if k['type'] == 'concealed' else '加杠'
            self_actions.append(f"可{label} [{k['tile']}] /{cmd}")
        if self_actions:
            msg += "\n" + "\n".join(self_actions)
        self.send_to(client, {'type': 'game', 'text': msg})
        self.send_to(client, {
            'type': 'hand_update',
            'hand': room.hands[pos], 'drawn': drawn_tile,
            'tenpai_analysis': room.get_tenpai_analysis(pos)
        })
        self_action_data = self._build_self_action_prompt(room, pos)
        if self_action_data:
            self.send_to(client, {'type': 'self_action_prompt', 'actions': self_action_data})
        if room.riichi[pos] and not (drawn_tile and room.can_win(room.hands[pos][:-1], drawn_tile)):
            self._schedule_riichi_auto_discard(room_id, player_name)

    def _send_invite_notification(self, target_name, invite_data):
        """发送邀请通知给指定玩家"""
        with self.lock:
            for client, info in self.clients.items():
                if info.get('name') == target_name and info.get('state') == 'playing':
                    self.send_to(client, invite_data)
                    break
    
    def _notify_room_players(self, room_id, message, room_data, exclude_player=None):
        """通知房间内所有玩家（message 嵌入 room_update）"""
        room = self._get_mahjong_room(room_id)
        if not room:
            return
        def send(client, name, pos):
            self.send_to(client, {'type': 'room_update', 'message': message, 'room_data': room_data})
        self._for_each_room_player(room, send, exclude_player)
    
    def _notify_room_update(self, room_id, message, room_data, exclude_player=None, update_last=False):
        """通知房间玩家（game 消息 + room_update 分开发送）"""
        room = self._get_mahjong_room(room_id)
        if not room:
            return
        def send(client, name, pos):
            if message:
                self.send_to(client, {'type': 'game', 'text': message, 'update_last': update_last})
            self.send_to(client, {'type': 'room_update', 'room_data': room_data})
        self._for_each_room_player(room, send, exclude_player)
    
    def _notify_room_win_animation(self, room_id, win_animation, room_data, exclude_player=None):
        """通知房间玩家显示胜利动画"""
        room = self._get_mahjong_room(room_id)
        if not room:
            return
        def send(client, name, pos):
            anims = win_animation if isinstance(win_animation, list) else [win_animation]
            for anim in anims:
                self.send_to(client, {'type': 'win_animation', **anim})
            if room_data:
                self.send_to(client, {'type': 'room_update', 'room_data': room_data})
        self._for_each_room_player(room, send, exclude_player)
    
    def _notify_room_players_with_hands(self, room_id, message, room_data, exclude_player=None, location=None):
        """通知房间玩家并发送各自手牌"""
        room = self._get_mahjong_room(room_id)
        if not room:
            return
        def send(client, name, pos):
            self.send_to(client, {'type': 'room_update', 'message': message, 'room_data': room_data})
            if location:
                self.send_to(client, {'type': 'location_update', 'location': location})
            self.send_to(client, {
                'type': 'hand_update', 'hand': room.hands[pos],
                'tenpai_analysis': room.get_tenpai_analysis(pos)
            })
        self._for_each_room_player(room, send, exclude_player)
    
    def _build_self_action_prompt(self, room, pos):
        """构建自摸/立直/暗杠/加杠的操作提示数据"""
        actions = {}
        hand = room.hands[pos]
        if not hand:
            return actions
        drawn_tile = hand[-1] if len(hand) % 3 == 2 else None
        if drawn_tile and room.can_win(hand[:-1], drawn_tile):
            actions['tsumo'] = True
        riichi_tiles = room.can_declare_riichi(pos)
        if riichi_tiles:
            actions['riichi'] = riichi_tiles
        for k in (room.check_self_kong(pos) or []):
            key = 'ankan' if k['type'] == 'concealed' else 'kakan'
            actions.setdefault(key, []).append(k)
        return actions
    
    def _broadcast_discard(self, room_id, discard_info, room_data, exclude_player=None):
        """通知房间内玩家有人打牌，检查吃碰杠，给下家发摸到的牌"""
        room = self._get_mahjong_room(room_id)
        if not room:
            return

        discard_player = discard_info.get('player', '')
        tile = discard_info.get('tile', '')
        next_player = discard_info.get('next_player', '')
        drawn_tile = discard_info.get('drawn_tile')
        waiting_action = discard_info.get('waiting_action', False)
        is_riichi = discard_info.get('is_riichi', False)

        action_hint = ""
        if waiting_action and hasattr(room, 'action_players') and room.action_players:
            action_hint = f" [等待操作({len(room.action_players)})]"
        if discard_player:
            prefix = f"{discard_player} 立直！打出" if is_riichi else f"{discard_player} 打出"
            base_msg = f"{prefix} [{tile}]，轮到 {next_player}{action_hint}"
        else:
            base_msg = None

        with self.lock:
            for client, info in self.clients.items():
                player_name = info.get('name')
                if player_name and player_name != exclude_player:
                    pos = room.get_position(player_name)
                    if pos < 0:
                        continue
                    self.send_to(client, {'type': 'room_update', 'room_data': room_data})
                    actions = room.check_actions(pos, tile) if tile else {}
                    if base_msg:
                        self.send_to(client, {'type': 'game', 'text': base_msg})

                    if player_name == next_player:
                        if waiting_action:
                            if actions:
                                self.send_to(client, {'type': 'action_prompt', 'actions': actions, 'tile': tile, 'from_player': discard_player})
                        elif drawn_tile:
                            self._send_draw_notification(client, room, room_id, pos, player_name, drawn_tile)
                    elif actions and any(k in actions for k in ('pong', 'kong', 'win')):
                        filtered = {k: v for k, v in actions.items() if k in ('pong', 'kong', 'win')}
                        self.send_to(client, {'type': 'action_prompt', 'actions': filtered, 'tile': tile, 'from_player': discard_player})

        if next_player and room.is_bot(next_player) and not waiting_action:
            self._schedule_bot_play(room_id, next_player)
        if waiting_action and hasattr(room, 'action_players') and room.action_players:
            self._schedule_bot_pass(room_id, tile, discard_player)
    
    def _schedule_riichi_auto_discard(self, room_id, player_name, delay=0.8):
        """安排立直玩家自动摸切"""
        # 创建定时器
        timer = threading.Timer(delay, self._riichi_auto_discard, args=[room_id, player_name])
        timer.start()
    
    def _riichi_auto_discard(self, room_id, player_name):
        """立直玩家自动摸切"""
        try:
            if 'mahjong' not in self.lobby_engine.game_engines:
                return
            
            engine = self.lobby_engine.game_engines['mahjong']
            room = engine.get_room(room_id)
            if not room or room.state != 'playing':
                return
            
            pos = room.get_position(player_name)
            if pos < 0:
                return
            
            # 确认是否轮到这个玩家且已立直
            if room.current_turn != pos or not room.riichi[pos]:
                return
            
            # 如果正在等待操作（别人可能要吃碰杠胡），不执行自动摸切
            if room.waiting_for_action:
                return
            
            hand = room.hands[pos]
            if not hand:
                return
            
            # 再次检查是否能自摸（防止延迟执行时状态变化）
            drawn_tile = hand[-1] if hand else None
            if drawn_tile and room.can_win(hand[:-1], drawn_tile):
                return  # 能自摸就不自动摸切
            
            # 打出最后一张牌（刚摸到的）
            tile_to_discard = hand[-1]
            
            # 执行打牌
            if not room.discard_tile(pos, tile_to_discard):
                return
            
            # 给立直玩家自己发送手牌更新
            with self.lock:
                for client, info in self.clients.items():
                    if info.get('name') == player_name:
                        # 通知自己打出了牌
                        self.send_to(client, {'type': 'game', 'text': f"🔒 立直中，自动摸切 [{tile_to_discard}]"})
                        # 发送手牌更新（没有新摸的牌）
                        tenpai_analysis = room.get_tenpai_analysis(pos)
                        self.send_to(client, {
                            'type': 'hand_update',
                            'hand': room.hands[pos],
                            'drawn': None,
                            'tenpai_analysis': tenpai_analysis
                        })
                        break
            
            # 构建弃牌信息
            next_pos = room.current_turn
            next_player = room.players[next_pos]
            
            # 检查是否有人可以吃碰杠
            if room.waiting_for_action:
                discard_info = {
                    'player': player_name,
                    'tile': tile_to_discard,
                    'next_player': next_player,
                    'drawn_tile': None,
                    'waiting_action': True
                }
                room_data = room.get_table_data()
                self._broadcast_discard(room_id, discard_info, room_data)
            else:
                drawn = room.draw_tile(next_pos)
                if drawn is None:
                    ryuukyoku_result = room.process_ryuukyoku('exhaustive')
                    room.state = 'finished'
                    self._broadcast_ryuukyoku(room_id, ryuukyoku_result, player_name, tile_to_discard)
                    return
                
                discard_info = {
                    'player': player_name,
                    'tile': tile_to_discard,
                    'next_player': next_player,
                    'drawn_tile': drawn,
                    'waiting_action': False
                }
                room_data = room.get_table_data()
                self._broadcast_discard(room_id, discard_info, room_data)
        except Exception as e:
            print(f"[立直 Error] {player_name} 自动摸切出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _schedule_bot_play(self, room_id, bot_name, delay=0.8):
        """安排机器人打牌"""
        # 取消之前的定时器
        if room_id in self.bot_timers:
            self.bot_timers[room_id].cancel()
        
        # 创建新定时器
        timer = threading.Timer(delay, self._bot_auto_play, args=[room_id, bot_name])
        self.bot_timers[room_id] = timer
        timer.start()
    
    def _bot_auto_play(self, room_id, bot_name):
        """机器人自动打牌"""
        try:
            if 'mahjong' not in self.lobby_engine.game_engines:
                return
            
            engine = self.lobby_engine.game_engines['mahjong']
            room = engine.get_room(room_id)
            if not room or room.state != 'playing':
                return
            
            # 确认是否轮到这个机器人
            current_player = room.get_current_player_name()
            if current_player != bot_name:
                return
            
            pos = room.get_position(bot_name)
            if pos < 0:
                return
            
            hand = room.hands[pos]
            if not hand:
                return
            
            # 使用智能 AI 决定打哪张牌
            from games.mahjong.bot_ai import get_bot_discard, get_bot_self_action
            
            # 先检查是否能自摸/立直
            self_actions = self._get_bot_self_actions(room, pos)
            if self_actions:
                action_result = get_bot_self_action(room, pos, self_actions)
                if action_result:
                    action_type, param = action_result
                    if action_type == 'tsumo':
                        # 执行自摸
                        self._bot_do_tsumo(room_id, bot_name, pos)
                        return
                    elif action_type == 'riichi':
                        # 执行立直
                        self._bot_do_riichi(room_id, bot_name, pos, param)
                        return
            
            # 决定打哪张牌
            tile_to_discard = get_bot_discard(room, pos)
            if not tile_to_discard:
                tile_to_discard = hand[-1]
            
            # 执行打牌
            result = room.discard_tile(pos, tile_to_discard)
            # 如果吃换禁止，换一张打
            if isinstance(result, tuple) and result[1] == 'kuikae':
                # 找一张不在禁止列表的牌
                from games.mahjong.game_data import normalize_tile
                forbidden = room.kuikae_forbidden[pos]
                for t in hand:
                    if normalize_tile(t) not in forbidden:
                        tile_to_discard = t
                        break
                result = room.discard_tile(pos, tile_to_discard, force=True)
            
            if not result or (isinstance(result, tuple) and not result[0]):
                return
            
            # 构建弃牌信息
            next_pos = room.current_turn
            next_player = room.players[next_pos]
            
            # 检查是否有人可以吃碰杠
            if room.waiting_for_action:
                discard_info = {
                    'player': bot_name,
                    'tile': tile_to_discard,
                    'next_player': next_player,
                    'drawn_tile': None,
                    'waiting_action': True
                }
                room_data = room.get_table_data()
                self._broadcast_discard(room_id, discard_info, room_data)
            else:
                drawn = room.draw_tile(next_pos)
                if drawn is None:
                    ryuukyoku_result = room.process_ryuukyoku('exhaustive')
                    room.state = 'finished'
                    self._broadcast_ryuukyoku(room_id, ryuukyoku_result, bot_name, tile_to_discard)
                    return
                
                discard_info = {
                    'player': bot_name,
                    'tile': tile_to_discard,
                    'next_player': next_player,
                    'drawn_tile': drawn,
                    'waiting_action': False
                }
                room_data = room.get_table_data()
                self._broadcast_discard(room_id, discard_info, room_data)
        except Exception as e:
            print(f"[Bot Error] {bot_name} 自动打牌出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_bot_self_actions(self, room, pos):
        """获取机器人可执行的自身操作"""
        actions = {}
        
        # 检查是否能自摸
        hand = room.hands[pos]
        if room.just_drew and hand:
            win_tile = hand[-1]
            if room.can_win(hand[:-1], win_tile):
                actions['tsumo'] = True
        
        # 检查是否能立直
        riichi_tiles = room.can_declare_riichi(pos)
        if riichi_tiles:
            actions['riichi'] = riichi_tiles
        
        return actions
    
    def _bot_do_tsumo(self, room_id, bot_name, pos):
        """机器人执行自摸"""
        engine = self.lobby_engine.game_engines['mahjong']
        room = engine.get_room(room_id)
        if not room:
            return
        
        hand = room.hands[pos]
        tsumo_tile = hand[-1]
        
        # 执行自摸结算
        result = room.process_win(pos, tsumo_tile, is_tsumo=True)
        
        if not result.get('success'):
            return
        
        room.state = 'finished'
        room.waiting_for_action = False
        
        room_data = room.get_table_data()
        
        # 发送胜利动画消息
        with self.lock:
            for client, info in self.clients.items():
                player_name = info.get('name')
                if not player_name:
                    continue
                client_pos = room.get_position(player_name)
                if client_pos < 0:
                    continue
                self.send_to(client, {
                    'type': 'win_animation',
                    'winner': bot_name,
                    'win_type': 'tsumo',
                    'tile': tsumo_tile,
                    'yakus': result['yakus'],
                    'han': result['han'],
                    'fu': result['fu'],
                    'score': result['score'],
                    'is_yakuman': result['is_yakuman']
                })
                self.send_to(client, {'type': 'room_update', 'room_data': room_data})
    
    def _bot_do_riichi(self, room_id, bot_name, pos, discard_tile):
        """机器人执行立直"""
        engine = self.lobby_engine.game_engines['mahjong']
        room = engine.get_room(room_id)
        if not room:
            return
        
        # 执行立直
        success, error = room.declare_riichi(pos, discard_tile)
        if not success:
            # 立直失败，改为普通打牌
            from games.mahjong.bot_ai import get_bot_discard
            tile_to_discard = get_bot_discard(room, pos)
            room.discard_tile(pos, tile_to_discard)
        else:
            # 立直成功
            message = f"{bot_name} 立直！"
            room_data = room.get_table_data()
            
            # 广播立直消息
            with self.lock:
                for client, info in self.clients.items():
                    player_name = info.get('name')
                    if not player_name:
                        continue
                    client_pos = room.get_position(player_name)
                    if client_pos < 0:
                        continue
                    self.send_to(client, {'type': 'game', 'text': message})
        
        # 继续处理下家
        next_pos = room.current_turn
        next_player = room.players[next_pos]
        
        if not room.waiting_for_action:
            drawn = room.draw_tile(next_pos)
            if drawn is None:
                ryuukyoku_result = room.process_ryuukyoku('exhaustive')
                room.state = 'finished'
                self._broadcast_ryuukyoku(room_id, ryuukyoku_result, bot_name, discard_tile)
                return
            
            discard_info = {
                'player': bot_name,
                'tile': discard_tile,
                'next_player': next_player,
                'drawn_tile': drawn,
                'waiting_action': False
            }
        else:
            discard_info = {
                'player': bot_name,
                'tile': discard_tile,
                'next_player': next_player,
                'drawn_tile': None,
                'waiting_action': True
            }
        
        room_data = room.get_table_data()
        self._broadcast_discard(room_id, discard_info, room_data)

    def _broadcast_ryuukyoku(self, room_id, ryuukyoku_result, last_discard_player=None, last_tile=None):
        """广播流局消息"""
        room = self._get_mahjong_room(room_id)
        if not room:
            return
        
        if room_id in self.bot_timers:
            self.bot_timers[room_id].cancel()
            del self.bot_timers[room_id]
        
        tenpai_names = [room.players[i] for i in ryuukyoku_result['tenpai']]
        noten_names = [room.players[i] for i in ryuukyoku_result['noten']]
        
        msg_lines = []
        if last_discard_player and last_tile:
            msg_lines.append(f"{last_discard_player} 打出 [{last_tile}]")
        msg_lines.append("荒牌流局！牌山已摸完")
        if tenpai_names:
            msg_lines.append(f"📗 听牌: {', '.join(tenpai_names)}")
        if noten_names:
            msg_lines.append(f"📕 未听: {', '.join(noten_names)}")
        for i in range(4):
            change = ryuukyoku_result['score_changes'][i]
            if change != 0:
                sign = '+' if change > 0 else ''
                msg_lines.append(f"  {room.players[i]}: {sign}{change}")
        if ryuukyoku_result.get('renchan'):
            msg_lines.append(f"🔄 {room.players[room.dealer]} 连庄")
        else:
            msg_lines.append("➡️ 轮庄")
        msg_lines += ["", "输入 /next 开始下一局", "输入 /back 返回上一级"]
        
        self._notify_room_update(room_id, '\n'.join(msg_lines), room.get_table_data())
    
    def _schedule_bot_pass(self, room_id, tile, from_player, delay=0.8):
        """安排机器人自动pass"""
        timer = threading.Timer(delay, self._bot_auto_pass, args=[room_id, tile, from_player])
        timer.start()
    
    def _bot_auto_pass(self, room_id, tile, from_player):
        """机器人自动pass所有等待操作"""
        try:
            if 'mahjong' not in self.lobby_engine.game_engines:
                return
            
            engine = self.lobby_engine.game_engines['mahjong']
            room = engine.get_room(room_id)
            if not room or room.state != 'playing':
                return
            
            if not room.waiting_for_action:
                return
            
            # 检查所有能操作的玩家，如果是bot就使用AI决策
            from games.mahjong.bot_ai import get_bot_action
            
            action_players = list(room.action_players) if hasattr(room, 'action_players') else []
            last_tile = room.last_discard
            
            for pos in action_players:
                player_name = room.players[pos]
                if not room.is_bot(player_name):
                    continue
                
                # 获取可用操作
                available_actions = room.check_actions(pos, last_tile)
                
                # AI决策
                action = get_bot_action(room, pos, last_tile, available_actions)
                
                if action == 'win':
                    # 执行荣和
                    self._bot_do_ron(room_id, player_name, pos, last_tile)
                    return
                elif action == 'pong':
                    # 执行碰
                    self._bot_do_pong(room_id, player_name, pos, last_tile)
                    return
                elif action == 'kong':
                    # 执行明杠
                    self._bot_do_kong(room_id, player_name, pos, last_tile)
                    return
                else:
                    # pass
                    if pos in room.action_players:
                        room.action_players.remove(pos)
                        # 广播更新后的等待人数
                        remaining = len(room.action_players)
                        next_player = room.players[room.current_turn]
                        self._notify_room_update(
                            room_id,
                            f"[等待操作({remaining})]，轮到 {next_player}",
                            room.get_table_data()
                        )
            
            # 如果所有人都pass了，让下家摸牌
            if not room.action_players:
                room.waiting_for_action = False
                next_pos = room.current_turn
                next_player = room.players[next_pos]
                
                # 下家摸牌
                drawn = room.draw_tile(next_pos)
                
                # 检查是否荒牌流局
                if drawn is None:
                    ryuukyoku_result = room.process_ryuukyoku('exhaustive')
                    room.state = 'finished'
                    self._broadcast_ryuukyoku(room_id, ryuukyoku_result)
                    return
                
                room_data = room.get_table_data()
                
                # 通知所有玩家
                self._notify_after_all_pass(room_id, next_player, drawn, room_data)
                
                # 如果下家是bot，安排自动打牌
                if room.is_bot(next_player):
                    self._schedule_bot_play(room_id, next_player)
        except Exception as e:
            print(f"[Bot Error] 自动pass出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _bot_do_ron(self, room_id, bot_name, pos, tile):
        """机器人执行荣和"""
        room = self._get_mahjong_room(room_id)
        if not room:
            return
        
        discarder_pos = room.last_discarder
        discarder_name = room.players[discarder_pos] if discarder_pos is not None else "?"
        result = room.process_win(pos, tile, is_tsumo=False, loser_pos=discarder_pos)
        if not result.get('success'):
            return
        
        room.state = 'finished'
        room.waiting_for_action = False
        room.action_players = []
        
        if discarder_pos is not None and room.discards[discarder_pos]:
            from games.mahjong.game_data import normalize_tile
            if normalize_tile(room.discards[discarder_pos][-1]) == normalize_tile(tile):
                room.discards[discarder_pos].pop()
        
        room_data = room.get_table_data()
        self._notify_room_win_animation(room_id, {
            'winner': bot_name, 'win_type': 'ron', 'tile': tile,
            'loser': discarder_name, 'yakus': result['yakus'],
            'han': result['han'], 'fu': result['fu'],
            'score': result['score'], 'is_yakuman': result['is_yakuman']
        }, room_data)
    
    def _bot_do_pong(self, room_id, bot_name, pos, tile):
        """机器人执行碰"""
        room = self._get_mahjong_room(room_id)
        if not room or not room.do_pong(pos, tile):
            return
        self._notify_room_update(room_id, f"{bot_name} 碰 [{tile}]", room.get_table_data())
        self._schedule_bot_play(room_id, bot_name, delay=0.8)
    
    def _bot_do_kong(self, room_id, bot_name, pos, tile):
        """机器人执行明杠"""
        room = self._get_mahjong_room(room_id)
        if not room:
            return
        success, need_draw = room.do_kong(pos, tile)
        if not success:
            return
        message = f"{bot_name} 杠 [{tile}]"
        if need_draw:
            drawn = room.draw_tile(pos, from_dead_wall=True)
            if drawn:
                message += "，岭上摸牌"
        self._notify_room_update(room_id, message, room.get_table_data())
        self._schedule_bot_play(room_id, bot_name, delay=0.8)

    def _notify_after_all_pass(self, room_id, next_player, drawn_tile, room_data):
        """通知所有人pass后的状态"""
        room = self._get_mahjong_room(room_id)
        if not room:
            return
        def send(client, player_name, pos):
            self.send_to(client, {'type': 'room_update', 'room_data': room_data})
            if player_name == next_player:
                self._send_draw_notification(client, room, room_id, pos, player_name, drawn_tile)
        self._for_each_room_player(room, send)

    def _get_log_file(self, channel):
        """获取当前日期的聊天记录文件路径"""
        return os.path.join(CHAT_LOG_DIR, f'channel_{channel}_{self.current_date}.json')

    def _check_and_archive_old_logs(self):
        """启动时检查并归档过期的聊天记录"""
        today = get_today_date_str()
        
        # 扫描 chat_logs 目录下的所有日志文件
        for filename in os.listdir(CHAT_LOG_DIR):
            if not filename.startswith('channel_') or not filename.endswith('.json'):
                continue
            
            # 解析文件名: channel_1_2025-12-20.json
            parts = filename.replace('.json', '').split('_')
            if len(parts) != 3:
                continue
            
            try:
                file_date = parts[2]  # 2025-12-20
                # 如果文件日期不是今天，需要归档
                if file_date != today:
                    channel = int(parts[1])
                    self._archive_old_log_file(channel, file_date)
            except:
                continue

    def _archive_old_log_file(self, channel, file_date):
        """归档指定日期的聊天记录"""
        log_file = os.path.join(CHAT_LOG_DIR, f'channel_{channel}_{file_date}.json')
        
        if not os.path.exists(log_file):
            return
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                messages = json.load(f)
            
            if messages:
                # 归档到 history 文件夹
                archive_file = os.path.join(CHAT_HISTORY_DIR, f'{file_date}_channel_{channel}.json')
                with open(archive_file, 'w', encoding='utf-8') as f:
                    json.dump(messages, f, ensure_ascii=False, indent=2)
                print(f"[启动归档] {file_date} 频道{channel} -> {archive_file}")
            
            # 删除旧的日志文件
            os.remove(log_file)
        except Exception as e:
            print(f"[启动归档] 归档失败 {log_file}: {e}")

    def _load_chat_logs(self):
        """加载当天的聊天记录"""
        # 先检查并归档过期的记录
        self._check_and_archive_old_logs()
        
        self.current_date = get_today_date_str()
        for channel in [1, 2]:
            log_file = self._get_log_file(channel)
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        self.chat_logs[channel] = json.load(f)
                except:
                    self.chat_logs[channel] = []
            else:
                self.chat_logs[channel] = []
        print(f"[聊天记录] 已加载 {self.current_date} 的记录")

    def _check_and_grant_time_titles(self, player_data):
        """检查并授予时间相关头衔"""
        from datetime import datetime
        now = datetime.now()
        
        titles = player_data.get('titles', {'owned': [], 'displayed': []})
        if 'owned' not in titles:
            titles['owned'] = []
        
        changed = False
        
        # 2025年早期玩家头衔
        if now.year == 2025 and '先驱者' not in titles['owned']:
            titles['owned'].append('先驱者')
            changed = True
        
        # 2025圣诞节头衔 (12月24-26日)
        if now.year == 2025 and now.month == 12 and 24 <= now.day <= 26:
            if '圣诞快乐' not in titles['owned']:
                titles['owned'].append('圣诞快乐')
                changed = True
        
        if changed:
            player_data['titles'] = titles
            PlayerManager.save_player_data(player_data['name'], player_data)

    def _save_chat_log(self, channel, name, text):
        """保存聊天记录"""
        now = get_beijing_now()
        msg = {
            'name': name, 
            'text': text, 
            'time': now.strftime('%H:%M:%S')
        }
        self.chat_logs[channel].append(msg)
        
        # 写入文件
        log_file = self._get_log_file(channel)
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(self.chat_logs[channel], f, ensure_ascii=False)
        except:
            pass

    def _archive_chat_logs(self):
        """归档聊天记录到历史文件夹"""
        yesterday = self.current_date
        print(f"[维护] 正在归档 {yesterday} 的聊天记录...")
        
        for channel in [1, 2]:
            log_file = self._get_log_file(channel)
            if os.path.exists(log_file) and self.chat_logs[channel]:
                # 归档到 history 文件夹
                archive_file = os.path.join(CHAT_HISTORY_DIR, f'{yesterday}_channel_{channel}.json')
                try:
                    with open(archive_file, 'w', encoding='utf-8') as f:
                        json.dump(self.chat_logs[channel], f, ensure_ascii=False, indent=2)
                    print(f"[维护] 频道{channel}归档完成: {archive_file}")
                except Exception as e:
                    print(f"[维护] 频道{channel}归档失败: {e}")
                
                # 删除旧的日志文件
                try:
                    os.remove(log_file)
                except:
                    pass
        
        # 清空内存中的记录
        self.chat_logs = {1: [], 2: []}
        # 更新日期
        self.current_date = get_today_date_str()
        print(f"[维护] 归档完成，新的一天开始: {self.current_date}")

    def _maintenance_loop(self):
        """维护检查循环"""
        while self.running:
            now = get_beijing_now()
            
            # 检查是否到了维护时间（凌晨4点）
            if now.hour == MAINTENANCE_HOUR and now.minute == 0:
                today = get_today_date_str()
                if today != self.current_date:
                    self._do_maintenance()
                    # 等待1分钟避免重复触发
                    time.sleep(60)
            
            time.sleep(30)  # 每30秒检查一次

    def _do_maintenance(self):
        """执行维护"""
        print("[维护] 系统维护开始...")
        
        # 通知所有玩家
        self.broadcast({
            'type': 'system',
            'text': '⚠️ 系统维护时间到，请在1分钟内保存数据并退出，服务器即将重置聊天记录...'
        })
        
        # 等待30秒
        time.sleep(30)
        
        # 再次通知
        self.broadcast({
            'type': 'system',
            'text': '⚠️ 系统维护中，正在归档聊天记录...'
        })
        
        # 断开所有客户端
        with self.lock:
            clients_to_close = list(self.clients.keys())
        
        for client in clients_to_close:
            try:
                self.send_to(client, {'type': 'action', 'action': 'maintenance'})
            except:
                pass
        
        # 等待客户端断开
        time.sleep(5)
        
        # 强制断开
        for client in clients_to_close:
            self.remove_client(client)
        
        # 归档聊天记录
        self._archive_chat_logs()
        
        print("[维护] 系统维护完成，服务器继续运行")

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def broadcast(self, message, exclude=None, channel=None):
        with self.lock:
            if channel:
                clients_to_send = [
                    c for c, info in self.clients.items() 
                    if c != exclude and info.get('channel') == channel
                ]
            else:
                clients_to_send = [c for c in self.clients.keys() if c != exclude]
        
        data = json.dumps(message) + '\n'
        for client in clients_to_send:
            try:
                client.send(data.encode('utf-8'))
            except:
                pass

    def send_to(self, client_socket, message):
        try:
            data = json.dumps(message) + '\n'
            client_socket.send(data.encode('utf-8'))
        except:
            pass

    def broadcast_online_users(self):
        users = []
        with self.lock:
            for info in self.clients.values():
                if info.get('state') == 'playing' and info.get('name'):
                    users.append({
                        'name': info['name'],
                        'channel': info.get('channel', 1)
                    })
        self.broadcast({'type': 'online_users', 'users': users})

    def handle_client(self, client_socket):
        buffer = ""
        
        with self.lock:
            self.clients[client_socket] = {
                'name': None, 'state': 'login', 'data': None, 'channel': 1
            }
        
        # 登录提示发到指令区
        self.send_to(client_socket, {'type': 'login_prompt', 'text': '请输入用户名：'})
        
        while self.running:
            try:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                
                buffer += data
                while '\n' in buffer:
                    msg_str, buffer = buffer.split('\n', 1)
                    if msg_str:
                        msg = json.loads(msg_str)
                        self.process_message(client_socket, msg)
            except:
                break
        
        self.remove_client(client_socket)

    def process_message(self, client_socket, msg):
        with self.lock:
            client_info = self.clients.get(client_socket)
        
        if not client_info:
            return
        
        state = client_info['state']
        msg_type = msg.get('type', 'command')
        text = msg.get('text', '').strip()
        
        if msg_type == 'switch_channel':
            channel = msg.get('channel', 1)
            with self.lock:
                self.clients[client_socket]['channel'] = channel
            # 发送该频道的聊天历史
            self._send_chat_history(client_socket, channel)
            self.broadcast_online_users()
            return
        
        if msg_type == 'avatar_update':
            # 处理头像更新
            avatar_data = msg.get('avatar')
            if avatar_data and state == 'playing':
                with self.lock:
                    player_data = self.clients[client_socket].get('data')
                    name = self.clients[client_socket].get('name')
                if player_data and name:
                    player_data['avatar'] = avatar_data
                    PlayerManager.save_player_data(name, player_data)
                    self.send_player_status(client_socket, player_data)
                    self.send_to(client_socket, {'type': 'game', 'text': '头像已更新！'})
            return
        
        if state == 'login':
            self._handle_login(client_socket, text)
        elif state == 'register_password':
            self._handle_register_password(client_socket, text)
        elif state == 'register':
            self._handle_register(client_socket, text)
        elif state == 'password':
            self._handle_password(client_socket, text)
        elif state == 'playing':
            self._handle_playing(client_socket, msg)

    def _send_chat_history(self, client_socket, channel):
        """发送聊天历史"""
        messages = self.chat_logs.get(channel, [])
        # 发送最近50条
        recent = messages[-50:] if len(messages) > 50 else messages
        self.send_to(client_socket, {
            'type': 'chat_history',
            'channel': channel,
            'messages': recent
        })

    def _handle_login(self, client_socket, text):
        # 检查是否是删除账号命令
        if text.startswith('/delete '):
            self._handle_delete_account(client_socket, text[8:])
            return
        
        if not text:
            self.send_to(client_socket, {'type': 'login_prompt', 'text': '用户名不能为空，请重新输入：'})
            return
        
        name = text
        exists = PlayerManager.player_exists(name)
        
        with self.lock:
            self.clients[client_socket]['name'] = name
        
        if exists:
            self.clients[client_socket]['state'] = 'password'
            self.send_to(client_socket, {'type': 'login_prompt', 'text': f'用户: {name}\n请输入密码（输入 /back 返回）：'})
        else:
            self.clients[client_socket]['state'] = 'register_password'
            self.send_to(client_socket, {'type': 'login_prompt', 'text': f'新用户: {name}\n请设置密码（至少3个字符，输入 /back 返回）：'})

    def _handle_delete_account(self, client_socket, args):
        """处理删除账号命令: /delete 用户名 密码"""
        parts = args.strip().split(' ', 1)
        if len(parts) < 2:
            self.send_to(client_socket, {
                'type': 'login_prompt',
                'text': '删除账号格式: /delete 用户名 密码\n请输入用户名：'
            })
            return
        
        name, password = parts[0], parts[1]
        
        # 检查用户是否存在
        if not PlayerManager.player_exists(name):
            self.send_to(client_socket, {
                'type': 'login_prompt',
                'text': f'用户 {name} 不存在\n请输入用户名：'
            })
            return
        
        # 尝试删除
        success, message = PlayerManager.delete_player(name, password)
        
        if success:
            self.send_to(client_socket, {
                'type': 'login_prompt',
                'text': f'{message}\n请输入用户名：'
            })
            print(f"[-] 账号已删除: {name}")
        else:
            self.send_to(client_socket, {
                'type': 'login_prompt',
                'text': f'✗ {message}\n请输入用户名：'
            })

    def _handle_register(self, client_socket, text):
        """处理注册 - 接收头像数据"""
        with self.lock:
            name = self.clients[client_socket]['name']
            temp_password = self.clients[client_socket].get('temp_password')
        
        # text 是头像数据
        avatar_data = text if text else None
        
        try:
            PlayerManager.register_player(name, temp_password, avatar_data)
            player_data = PlayerManager.load_player_data(name)
        except Exception as e:
            print(f"[!] 注册失败 {name}: {e}")
            self.send_to(client_socket, {'type': 'login_prompt', 'text': f'注册失败，请重试。\n请输入用户名：'})
            with self.lock:
                self.clients[client_socket]['state'] = 'login'
                self.clients[client_socket]['name'] = None
            return
        
        with self.lock:
            self.clients[client_socket]['state'] = 'playing'
            self.clients[client_socket]['data'] = player_data
            if 'temp_password' in self.clients[client_socket]:
                del self.clients[client_socket]['temp_password']
        
        self.send_to(client_socket, {'type': 'login_success', 'text': f'注册成功！输入 /help 查看指令。'})
        self.send_player_status(client_socket, player_data)
        
        # 注册到游戏大厅引擎（用于邀请功能）
        self.lobby_engine.register_player(name, player_data)
        
        # 发送聊天历史
        self._send_chat_history(client_socket, 1)
        
        # 聊天室显示上线消息
        online_msg = f'{name} 上线了'
        self._save_chat_log(1, '[SYS]', online_msg)
        self.broadcast({'type': 'chat', 'name': '[SYS]', 'text': online_msg, 'channel': 1})
        
        self.broadcast_online_users()
        print(f"[+] {name} 注册并加入")

    def _handle_register_password(self, client_socket, text):
        """处理注册 - 设置密码"""
        # 支持返回
        if text.lower() == '/back':
            with self.lock:
                self.clients[client_socket]['state'] = 'login'
                self.clients[client_socket]['name'] = None
            self.send_to(client_socket, {'type': 'login_prompt', 'text': '请输入用户名：'})
            return
        
        if len(text) < 3:
            self.send_to(client_socket, {'type': 'login_prompt', 'text': '密码至少3个字符，请重新输入（/back 返回）：'})
            return
        
        with self.lock:
            self.clients[client_socket]['temp_password'] = text
            self.clients[client_socket]['state'] = 'register'
        
        # 通知客户端打开头像编辑器
        self.send_to(client_socket, {'type': 'request_avatar', 'text': '请绘制你的像素头像！'})

    def _handle_password(self, client_socket, text):
        # 支持返回
        if text.lower() == '/back':
            with self.lock:
                self.clients[client_socket]['state'] = 'login'
                self.clients[client_socket]['name'] = None
            self.send_to(client_socket, {'type': 'login_prompt', 'text': '请输入用户名：'})
            return
        
        with self.lock:
            name = self.clients[client_socket]['name']
        
        if PlayerManager.verify_password(name, text):
            player_data = PlayerManager.load_player_data(name)
            
            # 检查并授予时间相关头衔
            self._check_and_grant_time_titles(player_data)
            
            with self.lock:
                self.clients[client_socket]['state'] = 'playing'
                self.clients[client_socket]['data'] = player_data
            
            self.send_to(client_socket, {'type': 'login_success', 'text': f'登录成功！输入 /help 查看指令。'})
            self.send_player_status(client_socket, player_data)
            
            # 注册到游戏大厅引擎（用于邀请功能）
            self.lobby_engine.register_player(name, player_data)
            
            # 发送聊天历史
            self._send_chat_history(client_socket, 1)
            
            # 聊天室显示上线消息
            online_msg = f'{name} 上线了'
            self._save_chat_log(1, '[SYS]', online_msg)
            self.broadcast({'type': 'chat', 'name': '[SYS]', 'text': online_msg, 'channel': 1})
            
            self.broadcast_online_users()
            print(f"[+] {name} 登录")
        else:
            self.send_to(client_socket, {'type': 'login_prompt', 'text': '密码错误，请重试（/back 返回）：'})

    def _send_result_fields(self, client_socket, result, **extra_msg_fields):
        """发送result中常见字段: message, hand, room_data, location"""
        if result.get('message'):
            msg_data = {'type': 'game', 'text': result['message']}
            msg_data.update(extra_msg_fields)
            self.send_to(client_socket, msg_data)
        if 'hand' in result:
            hand_data = {'type': 'hand_update', 'hand': result['hand']}
            for key in ('drawn', 'tenpai_analysis', 'need_discard'):
                if key in result:
                    hand_data[key] = result[key]
            self.send_to(client_socket, hand_data)
        if 'room_data' in result:
            self.send_to(client_socket, {'type': 'room_update', 'room_data': result['room_data']})
        if 'location' in result:
            self.send_to(client_socket, {'type': 'location_update', 'location': result['location']})

    def _handle_playing(self, client_socket, msg):
        with self.lock:
            name = self.clients[client_socket]['name']
            player_data = self.clients[client_socket]['data']
            client_channel = self.clients[client_socket].get('channel', 1)
        
        msg_type = msg.get('type', 'command')
        text = msg.get('text', '').strip()
        
        if msg_type == 'command':
            result = self.lobby_engine.process_command(player_data, text)
            if result:
                if isinstance(result, dict) and 'action' in result:
                    action = result['action']
                    if action == 'clear':
                        self.send_to(client_socket, {'type': 'action', 'action': 'clear'})
                    elif action == 'version':
                        # 版本信息
                        self.send_to(client_socket, {
                            'type': 'action',
                            'action': 'version',
                            'server_version': result.get('server_version', '未知')
                        })
                    elif action == 'confirm_prompt':
                        # 确认提示（如退出游戏确认），需要清除出牌状态
                        self.send_to(client_socket, {'type': 'game', 'text': result.get('message', ''), 'clear_discard': True})
                    elif action == 'exit':
                        self.send_to(client_socket, {'type': 'action', 'action': 'exit'})
                        PlayerManager.save_player_data(name, player_data)
                    elif action == 'request_avatar':
                        # 请求修改头像
                        self.send_to(client_socket, {'type': 'request_avatar', 'text': '请绘制你的新头像！'})
                    elif action == 'rename_success':
                        # 改名成功
                        old_name = result.get('old_name')
                        new_name = result.get('new_name')
                        # 更新客户端信息
                        self.clients[client_socket]['name'] = new_name
                        self.send_to(client_socket, {'type': 'game', 'text': result.get('message', '')})
                        PlayerManager.save_player_data(new_name, player_data)
                        self.send_player_status(client_socket, player_data)
                        # 广播改名消息
                        self.broadcast({'type': 'chat', 'name': '[SYS]', 'text': f'{old_name} 改名为 {new_name}', 'channel': 1})
                    elif action == 'account_deleted':
                        # 账号已删除
                        self.send_to(client_socket, {'type': 'game', 'text': result.get('message', '')})
                        self.send_to(client_socket, {'type': 'action', 'action': 'exit'})
                    elif action == 'mahjong_room_update':
                        self._send_result_fields(client_socket, result)
                        if 'notify_room' in result:
                            notify = result['notify_room']
                            self._notify_room_players(
                                notify['room_id'],
                                notify.get('message', ''),
                                notify.get('room_data'),
                                exclude_player=name
                            )
                        PlayerManager.save_player_data(name, player_data)
                        self.send_player_status(client_socket, player_data)
                    elif action == 'mahjong_bot_join':
                        self._send_result_fields(client_socket, result)
                        if 'notify_room' in result:
                            notify = result['notify_room']
                            self._notify_room_players(
                                notify['room_id'],
                                notify.get('message', ''),
                                notify.get('room_data'),
                                exclude_player=name
                            )
                    elif action == 'mahjong_room_leave':
                        # 离开麻将房间
                        self.send_to(client_socket, {'type': 'game', 'text': result.get('message', '')})
                        self.send_to(client_socket, {'type': 'room_leave'})
                        # 通知房间内其他玩家
                        if 'notify_room' in result:
                            notify = result['notify_room']
                            self._notify_room_players(
                                notify['room_id'],
                                notify.get('message', ''),
                                notify.get('room_data'),
                                exclude_player=name
                            )
                        PlayerManager.save_player_data(name, player_data)
                        self.send_player_status(client_socket, player_data)
                    elif action == 'game_quit':
                        # 退出游戏返回大厅
                        self.send_to(client_socket, {'type': 'game', 'text': result.get('message', '')})
                        self.send_to(client_socket, {'type': 'game_quit'})
                        PlayerManager.save_player_data(name, player_data)
                        self.send_player_status(client_socket, player_data)
                    elif action == 'mahjong_game_start':
                        self._send_result_fields(client_socket, result)
                        if 'notify_room' in result:
                            notify = result['notify_room']
                            self._notify_room_players_with_hands(
                                notify['room_id'],
                                notify.get('message', ''),
                                notify.get('room_data'),
                                exclude_player=name,
                                location=notify.get('location')  # 传递位置信息
                            )
                        # 检查庄家是否是机器人，如果是则启动自动打牌
                        room_id = result.get('room_id')
                        dealer_name = result.get('dealer_name')
                        if room_id and dealer_name:
                            engine = self.lobby_engine.game_engines.get('mahjong')
                            if engine:
                                room = engine.get_room(room_id)
                                if room and room.is_bot(dealer_name):
                                    self._schedule_bot_play(room_id, dealer_name)
                        PlayerManager.save_player_data(name, player_data)
                    elif action == 'mahjong_hand_update':
                        self._send_result_fields(client_socket, result)
                    elif action == 'mahjong_discard':
                        self._send_result_fields(client_socket, result)
                        # 通知其他玩家并给下家发摸到的牌
                        if 'notify_room' in result:
                            notify = result['notify_room']
                            self._broadcast_discard(
                                notify['room_id'],
                                notify.get('discard_info', {}),
                                notify.get('room_data'),
                                exclude_player=name
                            )
                    elif action in ['mahjong_pong', 'mahjong_kong', 'mahjong_chow']:
                        self._send_result_fields(client_socket, result)
                        # 通知房间内其他玩家
                        if 'notify_room' in result:
                            notify = result['notify_room']
                            self._notify_room_update(
                                notify['room_id'],
                                notify.get('message', ''),
                                notify.get('room_data'),
                                exclude_player=name
                            )
                    elif action == 'mahjong_pass_complete':
                        # 所有人都pass了，通知下家摸牌
                        if result.get('message'):
                            self.send_to(client_socket, {'type': 'game', 'text': result.get('message', '')})
                        if 'room_data' in result:
                            self.send_to(client_socket, {
                                'type': 'room_update',
                                'room_data': result['room_data']
                            })
                        # 先通知所有人等待操作变为0
                        if 'notify_room' in result:
                            notify = result['notify_room']
                            discard_info = notify.get('discard_info', {})
                            next_player = discard_info.get('next_player', '')
                            drawn_tile = discard_info.get('drawn_tile')
                            
                            # 发送消息给所有人
                            self._notify_room_update(
                                notify['room_id'],
                                notify.get('message', ''),
                                notify.get('room_data'),
                                exclude_player=name
                            )
                            
                            # 如果下家就是执行pass的玩家自己，直接发送摸牌通知
                            if next_player == name and drawn_tile:
                                engine = self.lobby_engine.game_engines.get('mahjong')
                                room = engine.get_room(notify['room_id']) if engine else None
                                if room:
                                    pos = room.get_position(name)
                                    if pos >= 0:
                                        self._send_draw_notification(client_socket, room, notify['room_id'], pos, name, drawn_tile)
                            
                            # 通知房间内其他玩家（不排除下家，但下家如果是自己已经处理过了）
                            self._broadcast_discard(
                                notify['room_id'],
                                discard_info,
                                notify.get('room_data'),
                                exclude_player=name
                            )
                    elif action == 'mahjong_pass':
                        # 某人pass但还有其他人可操作
                        if result.get('message'):
                            self.send_to(client_socket, {'type': 'game', 'text': result.get('message', '')})
                        # 通知房间其他人（更新最后一行）
                        if 'notify_room' in result:
                            notify = result['notify_room']
                            self._notify_room_update(
                                notify['room_id'],
                                notify.get('message', ''),
                                notify.get('room_data'),
                                exclude_player=name,
                                update_last=True
                            )
                    elif action == 'mahjong_ryuukyoku':
                        self._send_result_fields(client_socket, result)
                        # 通知房间所有人
                        if 'notify_room' in result:
                            notify = result['notify_room']
                            self._notify_room_update(
                                notify['room_id'],
                                notify.get('message', ''),
                                notify.get('room_data'),
                                exclude_player=name
                            )
                    elif action == 'mahjong_win':
                        win_anim = result.get('win_animation')
                        if win_anim:
                            anims = win_anim if isinstance(win_anim, list) else [win_anim]
                            for anim in anims:
                                self.send_to(client_socket, {'type': 'win_animation', **anim})
                        if 'room_data' in result:
                            self.send_to(client_socket, {'type': 'room_update', 'room_data': result['room_data']})
                        if 'notify_room' in result:
                            notify = result['notify_room']
                            if 'win_animation' in notify:
                                self._notify_room_win_animation(
                                    notify['room_id'], notify['win_animation'],
                                    notify.get('room_data'), exclude_player=name
                                )
                    elif action in ['mahjong_riichi', 'mahjong_ankan', 'mahjong_kakan', 'mahjong_tsumo', 'mahjong_ron', 'mahjong_chankan']:
                        self._send_result_fields(client_socket, result)
                        # 通知房间内其他玩家
                        if 'notify_room' in result:
                            notify = result['notify_room']
                            self._notify_room_update(
                                notify['room_id'],
                                notify.get('message', ''),
                                notify.get('room_data'),
                                exclude_player=name
                            )
                        # 如果是杠操作，可能需要通知玩家摸牌
                        if 'notify_draw' in result:
                            notify = result['notify_draw']
                            room_id = notify['room_id']
                            # 发送给执行杠的玩家（自己），让他摸牌
                            if 'draw_tile' in notify:
                                self.send_to(client_socket, {
                                    'type': 'game',
                                    'text': f"你从岭上摸到: {notify['draw_tile']}"
                                })
                    elif action == 'location_update':
                        self._send_result_fields(client_socket, result)
                        PlayerManager.save_player_data(name, player_data)
                        self.send_player_status(client_socket, player_data)
                    elif action == 'back_to_game':
                        # 返回游戏（从房间返回大厅等）
                        if result.get('message'):
                            self.send_to(client_socket, {'type': 'game', 'text': result.get('message', '')})
                        self.send_to(client_socket, {
                            'type': 'room_leave',
                            'location': result.get('location')
                        })
                        # 通知房间内其他玩家
                        if 'notify_room' in result:
                            notify = result['notify_room']
                            self._notify_room_players(
                                notify['room_id'],
                                notify.get('message', ''),
                                notify.get('room_data'),
                                exclude_player=name
                            )
                        PlayerManager.save_player_data(name, player_data)
                        self.send_player_status(client_socket, player_data)
                    elif action == 'mahjong_game_end':
                        self._send_result_fields(client_socket, result)
                        # 通知房间内其他玩家
                        if 'notify_room' in result:
                            notify = result['notify_room']
                            self._notify_room_update(
                                notify['room_id'],
                                notify.get('message', ''),
                                notify.get('room_data'),
                                exclude_player=name
                            )
                        PlayerManager.save_player_data(name, player_data)
                        self.send_player_status(client_socket, player_data)
                else:
                    self.send_to(client_socket, {'type': 'game', 'text': result})
                    PlayerManager.save_player_data(name, player_data)
                    self.send_player_status(client_socket, player_data)
            else:
                self.send_to(client_socket, {'type': 'game', 'text': '未知指令。输入 /help 查看帮助。'})
        
        elif msg_type == 'chat':
            channel = msg.get('channel', 1)
            display_name = f"[Lv.{player_data['level']}]{name}"
            
            # 保存聊天记录
            self._save_chat_log(channel, display_name, text)
            
            # 获取当前时间
            import datetime
            current_time = datetime.datetime.now().strftime('%H:%M')
            
            # 广播给同频道的人
            chat_msg = {
                'type': 'chat',
                'name': display_name,
                'text': text,
                'channel': channel,
                'time': current_time  # 添加时间戳
            }
            self.broadcast(chat_msg, channel=channel)
            print(f"[CH{channel}][{name}] {text}")

    def send_player_status(self, client_socket, player_data):
        """发送游戏大厅状态"""
        try:
            # 游戏大厅的状态数据
            status_data = {
                'name': player_data['name'],
                'level': player_data['level'],
                'gold': player_data['gold'],
                'title': player_data.get('title', '新人'),
                'accessory': player_data.get('accessory'),
                'avatar': player_data.get('avatar')
            }
            
            # 获取JRPG游戏数据用于地图显示（如果在玩JRPG）
            jrpg_data = player_data.get('games', {}).get('jrpg', {})
            current_area = jrpg_data.get('current_area', 'forest')
            map_data = self.game_data.get_map(current_area)
            
            self.send_to(client_socket, {
                'type': 'status',
                'data': status_data,
                'area': current_area,
                'map': map_data
            })
        except:
            pass

    def remove_client(self, client_socket):
        name = None
        should_broadcast = False
        room_to_notify = None
        
        with self.lock:
            if client_socket in self.clients:
                info = self.clients[client_socket]
                name = info.get('name')
                
                if info.get('data'):
                    PlayerManager.save_player_data(name, info['data'])
                
                del self.clients[client_socket]
                
                try:
                    client_socket.close()
                except:
                    pass
                
                if name and info.get('state') == 'playing':
                    print(f"[-] {name} 离开")
                    should_broadcast = True
                    
                    # 从游戏引擎中注销玩家
                    self.lobby_engine.unregister_player(name)
                    
                    # 检查是否在麻将房间中
                    if 'mahjong' in self.lobby_engine.game_engines:
                        engine = self.lobby_engine.game_engines['mahjong']
                        room = engine.get_player_room(name)
                        if room:
                            room_to_notify = {
                                'room_id': room.room_id,
                                'message': f"{name} 离开了房间（下线）",
                            }
                            engine.leave_room(name)
                            # 重新获取房间数据（可能已删除）
                            updated_room = engine.get_room(room_to_notify['room_id'])
                            if updated_room:
                                room_to_notify['room_data'] = updated_room.get_table_data()
        
        if should_broadcast:
            # 聊天室显示下线消息
            offline_msg = f'{name} 下线了'
            self._save_chat_log(1, '[SYS]', offline_msg)
            self.broadcast({'type': 'chat', 'name': '[SYS]', 'text': offline_msg, 'channel': 1})
            self.broadcast_online_users()
            
            # 通知房间内其他玩家
            if room_to_notify and room_to_notify.get('room_data'):
                self._notify_room_players(
                    room_to_notify['room_id'],
                    room_to_notify['message'],
                    room_to_notify['room_data'],
                    exclude_player=name
                )

    def start(self):
        self.running = True
        self.server.bind((HOST, PORT))
        self.server.listen(10)
        
        # 启动时升级所有用户数据到最新模板
        from .player_manager import PlayerManager
        total, updated = PlayerManager.upgrade_all_users()
        if total > 0:
            print(f"[用户数据检查] 共 {total} 个用户，已更新 {updated} 个")
        
        # 启动维护检查线程
        self.maintenance_thread = threading.Thread(target=self._maintenance_loop)
        self.maintenance_thread.daemon = True
        self.maintenance_thread.start()
        
        ip = self.get_local_ip()
        print("=" * 40)
        print("JRPG聊天室服务器已启动")
        print(f"地址: {ip}:{PORT}")
        print(f"当前日期: {self.current_date}")
        print(f"维护时间: 每日北京时间 {MAINTENANCE_HOUR}:00")
        print("=" * 40)
        
        while self.running:
            try:
                client, addr = self.server.accept()
                thread = threading.Thread(target=self.handle_client, args=(client,))
                thread.daemon = True
                thread.start()
            except:
                break

    def stop(self):
        self.running = False
        self.server.close()
