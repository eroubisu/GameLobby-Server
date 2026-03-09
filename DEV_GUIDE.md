# 开发规范

> **本文件是项目的约定俗成记录，作为 AI 的持久记忆。所有开发必须遵守这些规范。**

## 交互规范

- 返回/取消统一用 `/back`
- 选择菜单支持 `/1`、`/2` 等编号

## UI 规范

### 颜色

```python
COLOR_BG_PRIMARY = '#1a1a1a'    # 主背景
COLOR_BG_SECONDARY = '#252525'  # 次级背景
COLOR_BG_TERTIARY = '#2d2d2d'   # 三级背景
COLOR_FG_PRIMARY = '#ffffff'    # 主文字
COLOR_FG_SECONDARY = '#b3b3b3'  # 次级文字
COLOR_FG_TERTIARY = '#808080'   # 三级文字
COLOR_ACCENT = '#0078d4'        # 强调色
```

### 滚动条

使用 `ModernScrollbar` 类（定义于 `client/ui.py`）

### 按钮

使用 `RoundedButton` 类，带圆角（`RADIUS_MEDIUM = 6`）

## 扩展指南

### 头衔

定义: `server/user_schema.py` → `TITLE_LIBRARY`

授予: `titles['owned'].append('头衔名')`

### 物品

定义: `server/user_schema.py` → `ITEM_LIBRARY`

增减: `inventory['item_id'] += 数量`

通用货币: `player_data['gold']`

### 游戏

1. 创建 `games/游戏名/` 目录
2. 在 `games/__init__.py` 的 `GAMES` 注册
3. 在 `lobby_engine.py` 的 `/play` 初始化引擎

## 位置系统

```
lobby
├── mahjong
│   ├── mahjong_room
│   └── mahjong_playing
├── jrpg
└── (其他游戏)
```
