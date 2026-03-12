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
from .user_schema import get_title_name, grant_title

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
        
        # Bot 调度器泛化注册：从 GAME_INFO 自动创建
        from games import GAMES
        self.bot_schedulers = {}
        for _gid, _mod in GAMES.items():
            _info = getattr(_mod, 'GAME_INFO', {})
            _create = _info.get('create_bot_scheduler')
            if _create:
                self.bot_schedulers[_gid] = _create(self)
        
        self.running = False
        self.chat_logs = {1: [], 2: []}  # 内存中的聊天记录
        self.current_date = get_today_date_str()  # 当前日期
        self.maintenance_thread = None
        self._load_chat_logs()
    
    # ── Rich Result 通用分发器 ──

    # 框架级消息类型 — 客户端核心直接处理，不包装
    _FRAMEWORK_MSG_TYPES = frozenset({
        'game', 'room_update', 'location_update', 'room_leave', 'game_quit',
        'status', 'online_users', 'chat', 'system', 'action',
        'login_prompt', 'login_success', 'request_avatar', 'chat_history',
        'game_invite', 'game_event',
    })

    def _wrap_game_event(self, msg, game_type):
        """将游戏特有消息自动包装为 game_event 信封。

        框架级消息（room_update/game/location_update 等）直接透传，
        游戏特有消息（hand_update/action_prompt/win_animation 等）包装为：
        {'type': 'game_event', 'game_type': ..., 'event': ..., 'data': {...}}
        """
        if not isinstance(msg, dict):
            return msg
        t = msg.get('type', '')
        if not t or t in self._FRAMEWORK_MSG_TYPES:
            return msg
        data = {k: v for k, v in msg.items() if k != 'type'}
        return {'type': 'game_event', 'game_type': game_type, 'event': t, 'data': data}

    def _resolve_game_type(self, caller_name):
        """从玩家位置推断当前游戏类型"""
        if not caller_name:
            return ''
        loc = self.lobby_engine.get_player_location(caller_name)
        gid = self.lobby_engine._get_game_for_location(loc)
        return gid or ''

    def dispatch_game_result(self, result, caller_socket=None, caller_name=None, caller_data=None):
        """通用游戏结果分发器 — Rich Result Protocol。

        游戏引擎返回 send_to_caller / send_to_players / schedule / save，
        本方法只做无脑投递，不解读游戏内容。
        游戏特有消息类型自动包装为 game_event 信封。
        """
        action = result.get('action', '') if isinstance(result, dict) else ''
        game_type = self._resolve_game_type(caller_name)

        # 1. send_to_caller
        if caller_socket:
            for msg in result.get('send_to_caller', []):
                msg = self._wrap_game_event(msg, game_type)
                self._inject_location_path(msg)
                self.send_to(caller_socket, msg)

        # 2. send_to_players
        for target, messages in result.get('send_to_players', {}).items():
            for msg in messages:
                msg = self._wrap_game_event(msg, game_type)
                self._inject_location_path(msg)
                self.send_to_player(target, msg)

        # 3. 位置变更：自动向 caller 发送 location_update / room_leave
        if caller_socket and caller_name and action in ('location_update', 'back_to_game'):
            loc, path = self._resolve_location(caller_name, result)
            msg_type = 'room_leave' if action == 'back_to_game' else 'location_update'
            loc_msg = {'type': msg_type, 'location': loc, 'location_path': path}
            self._inject_location_path(loc_msg)
            self.send_to(caller_socket, loc_msg)

        # 4. schedule
        for task in result.get('schedule', []):
            gid = task.get('game_id', '')
            sched = self.bot_schedulers.get(gid)
            if sched and hasattr(sched, 'handle_schedule'):
                sched.handle_schedule(task)

        # 5. save / status
        if caller_name and caller_data:
            PlayerManager.save_player_data(caller_name, caller_data)
            if caller_socket:
                self.send_player_status(caller_socket, caller_data)

    def _inject_location_path(self, msg):
        """为 location_update/room_leave 消息注入面包屑路径和指令列表"""
        if isinstance(msg, dict) and msg.get('type') in ('location_update', 'room_leave'):
            loc = msg.get('location')
            if loc:
                if 'location_path' not in msg:
                    msg['location_path'] = self.lobby_engine.get_location_path(loc)
                if 'commands' not in msg:
                    msg['commands'] = self.lobby_engine.get_commands_for_location(loc)

    def send_to_player(self, player_name, data):
        """发送消息给指定玩家（Bot调度器回调接口）"""
        with self.lock:
            for client, info in self.clients.items():
                if info.get('name') == player_name:
                    self.send_to(client, data)
                    break

    def _send_invite_notification(self, target_name, invite_data):
        """发送邀请通知给指定玩家"""
        with self.lock:
            for client, info in self.clients.items():
                if info.get('name') == target_name and info.get('state') == 'playing':
                    self.send_to(client, invite_data)
                    break

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
        
        # 2025年早期玩家头衔
        created_at = player_data.get('created_at', '')
        if created_at.startswith('2025'):
            grant_title(player_data, 'early_bird')
        
        # 2025圣诞节头衔
        if now.year == 2025 and now.month == 12 and 24 <= now.day <= 26:
            grant_title(player_data, 'christmas_2025')

    def _track_login_day(self, player_data):
        """记录登录天数并检查veteran头衔"""
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        
        social_stats = player_data.get('social_stats', {})
        last_login = social_stats.get('last_login_date', '')
        
        if today != last_login:
            social_stats['last_login_date'] = today
            social_stats['login_days'] = social_stats.get('login_days', 0) + 1
            player_data['social_stats'] = social_stats
            
            if social_stats['login_days'] >= 30:
                grant_title(player_data, 'veteran')
            
            PlayerManager.save_player_data(player_data['name'], player_data)

    def _track_chat_message(self, player_name, player_data):
        """记录聊天消息数并检查chat_active头衔"""
        social_stats = player_data.get('social_stats', {})
        social_stats['chat_messages'] = social_stats.get('chat_messages', 0) + 1
        player_data['social_stats'] = social_stats
        
        if social_stats['chat_messages'] >= 1000:
            grant_title(player_data, 'chat_active')

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
            'text': '⚠ 系统维护时间到，请在1分钟内保存数据并退出，服务器即将重置聊天记录...'
        })
        
        # 等待30秒
        time.sleep(30)
        
        # 再次通知
        self.broadcast({
            'type': 'system',
            'text': '⚠ 系统维护中，正在归档聊天记录...'
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
            avatar_data = msg.get('avatar') or None
            if state == 'register':
                # 注册流程：将头像数据传给 _handle_register
                self._handle_register(client_socket, avatar_data)
                return
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
        
        self.send_to(client_socket, {'type': 'login_success', 'text': f'注册成功！'})
        self.send_player_status(client_socket, player_data)
        
        # 注册到游戏大厅引擎（用于邀请功能）
        self.lobby_engine.register_player(name, player_data)
        
        # 下发初始位置指令集
        self._send_initial_location(client_socket, name)
        
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
            
            # 记录登录天数
            self._track_login_day(player_data)
            
            with self.lock:
                self.clients[client_socket]['state'] = 'playing'
                self.clients[client_socket]['data'] = player_data
            
            self.send_to(client_socket, {'type': 'login_success', 'text': f'登录成功！'})
            self.send_player_status(client_socket, player_data)
            
            # 注册到游戏大厅引擎（用于邀请功能）
            self.lobby_engine.register_player(name, player_data)
            
            # 下发初始位置指令集
            self._send_initial_location(client_socket, name)
            
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

    def _send_initial_location(self, client_socket, name):
        """登录成功后下发初始位置（含指令列表）"""
        loc = self.lobby_engine.get_player_location(name)
        msg = {
            'type': 'location_update',
            'location': loc,
            'location_path': self.lobby_engine.get_location_path(loc, name),
        }
        self._inject_location_path(msg)
        self.send_to(client_socket, msg)

    def _resolve_location(self, name, result):
        """从 result 或 lobby 获取当前位置和面包屑"""
        loc = result.get('location') if isinstance(result, dict) else None
        if not loc:
            loc = self.lobby_engine.get_player_location(name)
        path = self.lobby_engine.get_location_path(loc, name) if loc else None
        return loc, path

    def _handle_simple_result(self, client_socket, name, player_data, result):
        """处理不含 send_to_caller/send_to_players 的简单游戏结果"""
        action = result.get('action', '')
        if result.get('message'):
            self.send_to(client_socket, {'type': 'game', 'text': result['message']})
        # 透传游戏特有事件（game_events 列表）
        for evt in result.get('game_events', []):
            self.send_to(client_socket, evt)
        if 'room_data' in result:
            self.send_to(client_socket, {'type': 'room_update', 'room_data': result['room_data']})
        if action == 'back_to_game':
            loc, path = self._resolve_location(name, result)
            loc_msg = {'type': 'room_leave', 'location': loc, 'location_path': path}
            self._inject_location_path(loc_msg)
            self.send_to(client_socket, loc_msg)
        elif action == 'location_update' or 'location' in result:
            loc, path = self._resolve_location(name, result)
            loc_msg = {'type': 'location_update', 'location': loc, 'location_path': path}
            self._inject_location_path(loc_msg)
            self.send_to(client_socket, loc_msg)
        PlayerManager.save_player_data(name, player_data)
        self.send_player_status(client_socket, player_data)

    def _dispatch_result(self, client_socket, name, player_data, result):
        """分发 lobby_engine.process_command 的结果"""
        if isinstance(result, dict) and 'action' in result:
            action = result['action']

            # ── 大厅级动作（不携带 game_id） ──
            if action == 'clear':
                self.send_to(client_socket, {'type': 'action', 'action': 'clear'})
            elif action == 'version':
                self.send_to(client_socket, {
                    'type': 'action', 'action': 'version',
                    'server_version': result.get('server_version', '未知')})
            elif action == 'confirm_prompt':
                self.send_to(client_socket, {
                    'type': 'game', 'text': result.get('message', '')})
            elif action == 'exit':
                self.send_to(client_socket, {'type': 'action', 'action': 'exit'})
                PlayerManager.save_player_data(name, player_data)
            elif action == 'request_avatar':
                self.send_to(client_socket, {'type': 'request_avatar', 'text': '请绘制你的新头像！'})
            elif action == 'rename_success':
                old_name = result.get('old_name')
                new_name = result.get('new_name')
                self.clients[client_socket]['name'] = new_name
                self.send_to(client_socket, {'type': 'game', 'text': result.get('message', '')})
                PlayerManager.save_player_data(new_name, player_data)
                self.send_player_status(client_socket, player_data)
                self.broadcast({'type': 'chat', 'name': '[SYS]',
                                'text': f'{old_name} 改名为 {new_name}', 'channel': 1})
            elif action == 'account_deleted':
                self.send_to(client_socket, {'type': 'game', 'text': result.get('message', '')})
                self.send_to(client_socket, {'type': 'action', 'action': 'exit'})

            # ── 通用游戏动作分发 ──
            else:
                if 'send_to_caller' in result or 'send_to_players' in result:
                    self.dispatch_game_result(result, client_socket, name, player_data)
                else:
                    self._handle_simple_result(client_socket, name, player_data, result)
        else:
            self.send_to(client_socket, {'type': 'game', 'text': result})
            PlayerManager.save_player_data(name, player_data)
            self.send_player_status(client_socket, player_data)

    def _handle_playing(self, client_socket, msg):
        with self.lock:
            name = self.clients[client_socket]['name']
            player_data = self.clients[client_socket]['data']
            client_channel = self.clients[client_socket].get('channel', 1)
        
        msg_type = msg.get('type', 'command')
        text = msg.get('text', '').strip()
        
        if msg_type == 'command':
            try:
                result = self.lobby_engine.process_command(player_data, text)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_to(client_socket, {'type': 'game', 'text': f'[服务器错误] {e}'})
                return
            if result:
                try:
                    self._dispatch_result(client_socket, name, player_data, result)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self.send_to(client_socket, {'type': 'game', 'text': f'[服务器错误] {e}'})
            else:
                self.send_to(client_socket, {'type': 'game', 'text': '未知指令。'})
        
        elif msg_type == 'save_layout':
            layout = msg.get('layout')
            if isinstance(layout, dict):
                if self.lobby_engine._validate_layout(layout):
                    player_data['window_layout'] = layout
                    PlayerManager.save_player_data(name, player_data)

        elif msg_type == 'chat':
            channel = msg.get('channel', 1)
            display_name = f"[Lv.{player_data['level']}]{name}"
            
            # 记录聊天统计并检查头衔
            self._track_chat_message(name, player_data)
            
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
            # 从 displayed 头衔列表取第一个ID，转为显示名
            displayed = player_data.get('titles', {}).get('displayed', ['newcomer'])
            title_id = displayed[0] if displayed else 'newcomer'
            status_data = {
                'name': player_data['name'],
                'level': player_data['level'],
                'gold': player_data['gold'],
                'title': get_title_name(title_id),
                'accessory': player_data.get('accessory'),
                'avatar': player_data.get('avatar'),
                'window_layout': player_data.get('window_layout'),
            }
            
            # 查询当前游戏引擎的附加状态
            player_name = player_data.get('name', '')
            location = self.lobby_engine.get_player_location(player_name)
            game_id = self.lobby_engine._get_game_for_location(location)
            extras = {}
            if game_id:
                engine = self.lobby_engine._get_engine(game_id, player_name)
                if engine and hasattr(engine, 'get_status_extras'):
                    extras = engine.get_status_extras(player_name, player_data) or {}
            
            status_msg = {'type': 'status', 'data': status_data}
            status_msg['location'] = location
            status_msg['location_path'] = self.lobby_engine.get_location_path(location, player_name)
            status_msg.update(extras)
            self.send_to(client_socket, status_msg)
        except:
            pass

    def remove_client(self, client_socket):
        name = None
        should_broadcast = False
        room_notifications = None
        
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
                    
                    # 从游戏引擎中注销玩家（处理判负、段位）并获取通知列表
                    room_notifications = self.lobby_engine.unregister_player(name)
        
        if should_broadcast:
            # 聊天室显示下线消息
            offline_msg = f'{name} 下线了'
            self._save_chat_log(1, '[SYS]', offline_msg)
            self.broadcast({'type': 'chat', 'name': '[SYS]', 'text': offline_msg, 'channel': 1})
            self.broadcast_online_users()
            
            # 通知房间内其他玩家
            for notif in (room_notifications or []):
                self.dispatch_game_result(notif)

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
        print("游戏大厅服务器已启动")
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
