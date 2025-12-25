"""
玩家数据管理
"""

import os
import json
import hashlib
from datetime import datetime
from .config import USERS_DIR
from .user_schema import get_default_user_template, ensure_user_schema, get_rank_name


class PlayerManager:
    """玩家数据管理 - 注册、登录、存档"""
    
    @staticmethod
    def hash_password(password):
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def _get_user_file(name):
        """获取用户文件路径"""
        return os.path.join(USERS_DIR, f'{name}.json')
    
    @staticmethod
    def check_player_exists(name):
        """检查玩家是否存在"""
        return os.path.exists(PlayerManager._get_user_file(name))
    
    @staticmethod
    def player_exists(name):
        """检查玩家是否存在（用于改名检查）"""
        return PlayerManager.check_player_exists(name)
    
    @staticmethod
    def register_player(name, password, avatar_data=None):
        """注册新玩家"""
        if PlayerManager.check_player_exists(name):
            return False
        
        # 创建用户数据（包含密码哈希）
        data = PlayerManager._create_initial_data(name, password, avatar_data)
        PlayerManager._save_user_file(name, data)
        return True
    
    @staticmethod
    def verify_password(name, password):
        """验证密码"""
        file_path = PlayerManager._get_user_file(name)
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            hashed = PlayerManager.hash_password(password)
            return data.get('password_hash') == hashed
        except:
            return False
    
    @staticmethod
    def _create_initial_data(name, password, avatar_data=None):
        """创建初始玩家数据 - 使用标准模板"""
        template = get_default_user_template(
            name=name,
            password_hash=PlayerManager.hash_password(password)
        )
        template['avatar'] = avatar_data
        return template
    
    @staticmethod
    def _save_user_file(name, data):
        """保存用户文件"""
        # 确保目录存在
        os.makedirs(USERS_DIR, exist_ok=True)
        file_path = PlayerManager._get_user_file(name)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def load_player_data(name):
        """加载玩家数据（不包含密码哈希）并确保数据完整性"""
        file_path = PlayerManager._get_user_file(name)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 确保用户数据包含所有必需属性
                updated_data, changes = ensure_user_schema(data)
                
                # 如果有变更，保存更新后的数据
                if changes:
                    print(f"[用户数据更新] {name}: {len(changes)} 个属性已补充")
                    PlayerManager._save_user_file(name, updated_data)
                
                # 返回数据时移除密码哈希（安全考虑）
                result = {k: v for k, v in updated_data.items() if k != 'password_hash'}
                return result
            except Exception as e:
                print(f"[错误] 加载用户数据失败 {name}: {e}")
                pass
        return None
    
    @staticmethod
    def save_player_data(name, data):
        """保存玩家数据"""
        file_path = PlayerManager._get_user_file(name)
        
        # 先读取原文件获取密码哈希（不要丢失）
        password_hash = None
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                password_hash = old_data.get('password_hash')
            except:
                pass
        
        # 确保密码哈希不丢失
        if password_hash:
            data['password_hash'] = password_hash
        
        PlayerManager._save_user_file(name, data)

    @staticmethod
    def rename_player(old_name, new_name):
        """重命名玩家"""
        old_file = PlayerManager._get_user_file(old_name)
        new_file = PlayerManager._get_user_file(new_name)
        
        if not os.path.exists(old_file):
            return False
        
        if os.path.exists(new_file):
            return False
        
        # 加载数据，更新名字，保存到新文件
        with open(old_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['name'] = new_name
        
        with open(new_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        os.remove(old_file)
        return True
    
    @staticmethod
    def change_password(name, new_password):
        """修改密码"""
        file_path = PlayerManager._get_user_file(name)
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['password_hash'] = PlayerManager.hash_password(new_password)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except:
            return False

    @staticmethod
    def delete_player(name):
        """删除玩家账号"""
        file_path = PlayerManager._get_user_file(name)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False

    @staticmethod
    def upgrade_all_users():
        """
        升级所有用户数据到最新模板
        用于服务器启动时或手动运行
        
        Returns:
            (total, updated): 总用户数, 更新的用户数
        """
        total = 0
        updated = 0
        
        if not os.path.exists(USERS_DIR):
            return 0, 0
        
        for filename in os.listdir(USERS_DIR):
            if not filename.endswith('.json'):
                continue
            
            name = filename[:-5]  # 去掉 .json
            total += 1
            
            # 加载用户数据（会自动补充缺失属性）
            data = PlayerManager.load_player_data(name)
            if data:
                # load_player_data 已经自动保存了更新后的数据
                updated += 1
        
        return total, updated

    @staticmethod
    def get_player_rank(name):
        """获取玩家麻将段位"""
        data = PlayerManager.load_player_data(name)
        if data and 'mahjong' in data:
            rank_id = data['mahjong'].get('rank', 'novice_1')
            return rank_id, get_rank_name(rank_id)
        return 'novice_1', '初心一'

    @staticmethod
    def get_player_titles(name):
        """获取玩家头衔列表"""
        data = PlayerManager.load_player_data(name)
        if data and 'titles' in data:
            return data['titles'].get('displayed', ['新人'])
        return ['新人']
