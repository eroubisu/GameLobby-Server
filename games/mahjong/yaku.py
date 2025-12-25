"""
役种判定模块 - 日本麻将役种系统
"""

from .game_data import (
    normalize_tile, get_tile_suit, get_tile_number, is_number_tile,
    is_honor_tile, is_terminal, is_yaojiu, YAOJIU, ROUTOU, JIHAI,
    KAZEHAI, SANGENPAI, GREEN_TILES, is_red_dora
)


class YakuResult:
    """役种结果"""
    def __init__(self):
        self.yakus = []  # [(役名, 番数, 是否役满)]
        self.total_han = 0
        self.is_yakuman = False
    
    def add(self, name, han, is_yakuman=False):
        self.yakus.append((name, han, is_yakuman))
        if is_yakuman:
            self.is_yakuman = True
        else:
            self.total_han += han
    
    def get_display(self):
        """获取显示文本"""
        lines = []
        for name, han, is_ym in self.yakus:
            if is_ym:
                lines.append(f"🌟 {name} (役满)")
            else:
                lines.append(f"✓ {name} ({han}番)")
        return lines


def analyze_hand(hand_tiles, melds, win_tile, is_tsumo, is_riichi, is_ippatsu,
                 is_rinshan, is_chankan, is_haitei, is_houtei,
                 is_tenhou, is_chihou, is_double_riichi,
                 player_wind, round_wind, dora_count=0, ura_dora_count=0, red_dora_count=0):
    """
    分析手牌的役种
    
    Args:
        hand_tiles: 手牌列表（不含副露，含和牌）
        melds: 副露列表 [{'type': 'pong'/'kong'/'chow', 'tiles': [...], 'concealed': bool}]
        win_tile: 和牌的那张牌
        is_tsumo: 是否自摸
        is_riichi: 是否立直
        is_ippatsu: 是否一发
        is_rinshan: 是否岭上开花（杠后摸牌胡）
        is_chankan: 是否抢杠
        is_haitei: 是否海底摸月（最后一张自摸）
        is_houtei: 是否河底捞鱼（最后一张荣和）
        is_tenhou: 是否天和
        is_chihou: 是否地和
        is_double_riichi: 是否双立直
        player_wind: 玩家自风 ('东'/'南'/'西'/'北')
        round_wind: 场风 ('东'/'南')
        dora_count: 宝牌数
        ura_dora_count: 里宝牌数
        red_dora_count: 赤宝牌数
        
    Returns:
        YakuResult
    """
    result = YakuResult()
    
    # 标准化手牌（赤牌转普通牌用于判断）
    normalized_hand = [normalize_tile(t) for t in hand_tiles]
    normalized_win = normalize_tile(win_tile)
    
    # 判断是否门清（无明副露）
    is_menzen = all(m.get('concealed', False) or m['type'] == 'concealed_kong' 
                    for m in melds) if melds else True
    
    # 解析手牌结构
    structures = parse_hand_structure(normalized_hand, melds)
    
    if not structures:
        # 检查特殊牌型：七对子、国士无双
        if check_chitoitsu(normalized_hand):
            structures = [{'type': 'chitoitsu', 'pairs': get_pairs(normalized_hand)}]
        elif check_kokushi(normalized_hand, normalized_win):
            result.add('国士无双', 0, is_yakuman=True)
            return result
    
    if not structures:
        return result  # 无法解析
    
    # 使用第一个有效结构（后续可优化为选最高番数）
    structure = structures[0]
    
    # ========== 役满 ==========
    
    # 天和/地和
    if is_tenhou:
        result.add('天和', 0, is_yakuman=True)
        return result
    if is_chihou:
        result.add('地和', 0, is_yakuman=True)
        return result
    
    # 四暗刻
    if check_suuankou(structure, melds, is_tsumo, win_tile):
        result.add('四暗刻', 0, is_yakuman=True)
        return result
    
    # 大三元
    if check_daisangen(structure, melds):
        result.add('大三元', 0, is_yakuman=True)
        return result
    
    # 小四喜/大四喜
    xiaosixi, dasixi = check_suushii(structure, melds)
    if dasixi:
        result.add('大四喜', 0, is_yakuman=True)
        return result
    if xiaosixi:
        result.add('小四喜', 0, is_yakuman=True)
        return result
    
    # 字一色
    if check_tsuuiisou(normalized_hand, melds):
        result.add('字一色', 0, is_yakuman=True)
        return result
    
    # 清老头
    if check_chinroutou(normalized_hand, melds):
        result.add('清老头', 0, is_yakuman=True)
        return result
    
    # 绿一色
    if check_ryuuiisou(hand_tiles, melds):
        result.add('绿一色', 0, is_yakuman=True)
        return result
    
    # 九莲宝灯
    if check_chuurenpoutou(normalized_hand, is_menzen):
        result.add('九莲宝灯', 0, is_yakuman=True)
        return result
    
    # 四杠子
    if check_suukantsu(melds):
        result.add('四杠子', 0, is_yakuman=True)
        return result
    
    # ========== 普通役 ==========
    
    # 立直
    if is_riichi:
        if is_double_riichi:
            result.add('双立直', 2)
        else:
            result.add('立直', 1)
    
    # 一发
    if is_ippatsu:
        result.add('一发', 1)
    
    # 门清自摸
    if is_tsumo and is_menzen:
        result.add('门清自摸', 1)
    
    # 岭上开花
    if is_rinshan:
        result.add('岭上开花', 1)
    
    # 抢杠
    if is_chankan:
        result.add('抢杠', 1)
    
    # 海底摸月/河底捞鱼
    if is_haitei:
        result.add('海底摸月', 1)
    if is_houtei:
        result.add('河底捞鱼', 1)
    
    # 七对子
    if structure.get('type') == 'chitoitsu':
        result.add('七对子', 2)
    else:
        # 标准形役种
        
        # 断幺九
        if check_tanyao(normalized_hand, melds):
            result.add('断幺九', 1)
        
        # 平和（门清限定）
        if is_menzen and check_pinfu(structure, normalized_win, player_wind, round_wind):
            result.add('平和', 1)
        
        # 一杯口（门清限定）
        if is_menzen:
            iipeikou_count = check_iipeikou(structure)
            if iipeikou_count == 2:
                result.add('二杯口', 3)
            elif iipeikou_count == 1:
                result.add('一杯口', 1)
        
        # 役牌
        yaku_count = check_yakuhai(structure, melds, player_wind, round_wind)
        for yaku_name in yaku_count:
            result.add(yaku_name, 1)
        
        # 三色同顺
        if check_sanshoku_doujun(structure, melds):
            result.add('三色同顺', 2 if is_menzen else 1)
        
        # 一气通贯
        if check_ikkitsuukan(structure, melds):
            result.add('一气通贯', 2 if is_menzen else 1)
        
        # 混全带幺九
        if check_chanta(structure, melds):
            result.add('混全带幺九', 2 if is_menzen else 1)
        
        # 纯全带幺九
        if check_junchan(structure, melds):
            result.add('纯全带幺九', 3 if is_menzen else 2)
        
        # 对对和
        if check_toitoi(structure, melds):
            result.add('对对和', 2)
        
        # 三暗刻
        if check_sanankou(structure, melds, is_tsumo, win_tile):
            result.add('三暗刻', 2)
        
        # 三杠子
        if check_sankantsu(melds):
            result.add('三杠子', 2)
        
        # 小三元
        if check_shousangen(structure, melds):
            result.add('小三元', 2)
        
        # 三色同刻
        if check_sanshoku_doukou(structure, melds):
            result.add('三色同刻', 2)
        
        # 混老头
        if check_honroutou(normalized_hand, melds):
            result.add('混老头', 2)
        
        # 混一色
        if check_honitsu(normalized_hand, melds):
            result.add('混一色', 3 if is_menzen else 2)
        
        # 清一色
        if check_chinitsu(normalized_hand, melds):
            result.add('清一色', 6 if is_menzen else 5)
    
    # 宝牌（无条件加番）
    if dora_count > 0:
        result.add(f'宝牌', dora_count)
    if ura_dora_count > 0:
        result.add(f'里宝牌', ura_dora_count)
    if red_dora_count > 0:
        result.add(f'赤宝牌', red_dora_count)
    
    return result


def parse_hand_structure(hand, melds):
    """
    解析手牌结构，返回可能的牌型列表
    每个牌型包含: pair(雀头), sets(面子列表)
    """
    results = []
    tile_count = {}
    for t in hand:
        tile_count[t] = tile_count.get(t, 0) + 1
    
    # 尝试每种牌作为雀头
    for pair_tile in list(tile_count.keys()):
        if tile_count[pair_tile] >= 2:
            remaining = tile_count.copy()
            remaining[pair_tile] -= 2
            if remaining[pair_tile] == 0:
                del remaining[pair_tile]
            
            sets = []
            if extract_melds(remaining, sets):
                results.append({
                    'type': 'standard',
                    'pair': pair_tile,
                    'sets': sets.copy(),
                    'melds': melds
                })
    
    return results


def extract_melds(tile_count, sets):
    """递归提取面子"""
    if not tile_count:
        return True
    
    # 获取第一张牌
    first_tile = min(tile_count.keys(), key=lambda t: (get_tile_suit(t) or '', get_tile_number(t) or 0))
    count = tile_count[first_tile]
    
    # 尝试刻子
    if count >= 3:
        remaining = tile_count.copy()
        remaining[first_tile] -= 3
        if remaining[first_tile] == 0:
            del remaining[first_tile]
        sets.append({'type': 'pon', 'tile': first_tile})
        if extract_melds(remaining, sets):
            return True
        sets.pop()
    
    # 尝试顺子（数牌）
    if is_number_tile(first_tile):
        suit = get_tile_suit(first_tile)
        num = get_tile_number(first_tile)
        if num <= 7:
            # 构建顺子
            tiles_needed = []
            for n in [num, num+1, num+2]:
                t = get_tile_by_suit_num(suit, n)
                tiles_needed.append(t)
            
            if all(t in tile_count and tile_count[t] >= 1 for t in tiles_needed):
                remaining = tile_count.copy()
                for t in tiles_needed:
                    remaining[t] -= 1
                    if remaining[t] == 0:
                        del remaining[t]
                sets.append({'type': 'chi', 'tiles': tiles_needed, 'start': first_tile})
                if extract_melds(remaining, sets):
                    return True
                sets.pop()
    
    return False


def get_tile_by_suit_num(suit, num):
    """根据花色和数字获取牌名"""
    from .game_data import get_tile_by_suit_number
    return get_tile_by_suit_number(suit, num)


def get_pairs(hand):
    """获取七对子的对子列表"""
    tile_count = {}
    for t in hand:
        tile_count[t] = tile_count.get(t, 0) + 1
    return [t for t, c in tile_count.items() if c >= 2]


# ========== 牌型检查函数 ==========

def check_chitoitsu(hand):
    """检查七对子: 7个不同的对子"""
    if len(hand) != 14:
        return False
    tile_count = {}
    for t in hand:
        tile_count[t] = tile_count.get(t, 0) + 1
    return len(tile_count) == 7 and all(c == 2 for c in tile_count.values())


def check_kokushi(hand, win_tile):
    """检查国士无双: 13种幺九牌各1张 + 任意1张幺九"""
    if len(hand) != 14:
        return False
    yaojiu_set = set(YAOJIU)
    hand_set = set(hand)
    if not yaojiu_set.issubset(hand_set):
        return False
    # 检查是否只有幺九牌
    for t in hand:
        if t not in yaojiu_set:
            return False
    return True


def check_tanyao(hand, melds):
    """检查断幺九: 全是中张（2-8）"""
    all_tiles = hand.copy()
    for m in melds:
        all_tiles.extend(m.get('tiles', []))
    return all(not is_yaojiu(normalize_tile(t)) for t in all_tiles)


def check_pinfu(structure, win_tile, player_wind, round_wind):
    """检查平和: 4顺子+非役牌雀头+两面听"""
    if structure.get('type') != 'standard':
        return False
    
    # 所有面子必须是顺子
    for s in structure.get('sets', []):
        if s['type'] != 'chi':
            return False
    
    # 雀头不能是役牌
    pair = structure['pair']
    if pair in SANGENPAI:
        return False
    if pair == player_wind or pair == round_wind:
        return False
    
    # TODO: 检查两面听（需要更多上下文）
    return True


def check_iipeikou(structure):
    """检查一杯口/二杯口: 相同的顺子"""
    if structure.get('type') != 'standard':
        return 0
    
    chi_sets = [tuple(s.get('tiles', [])) for s in structure.get('sets', []) if s['type'] == 'chi']
    
    # 计算重复顺子对数
    count = {}
    for c in chi_sets:
        count[c] = count.get(c, 0) + 1
    
    pairs = sum(c // 2 for c in count.values())
    return pairs


def check_yakuhai(structure, melds, player_wind, round_wind):
    """检查役牌，返回役牌名列表"""
    yakus = []
    
    # 收集所有刻子/杠子
    pon_tiles = []
    for s in structure.get('sets', []):
        if s['type'] == 'pon':
            pon_tiles.append(s['tile'])
    for m in melds:
        if m['type'] in ('pong', 'kong', 'concealed_kong'):
            pon_tiles.append(m['tiles'][0])
    
    for tile in pon_tiles:
        if tile == '中':
            yakus.append('役牌:中')
        elif tile == '发':
            yakus.append('役牌:发')
        elif tile == '白':
            yakus.append('役牌:白')
        elif tile == player_wind:
            yakus.append(f'自风:{tile}')
        elif tile == round_wind:
            yakus.append(f'场风:{round_wind}')
    
    return yakus


def check_sanshoku_doujun(structure, melds):
    """检查三色同顺: 万条筒各有相同数字的顺子"""
    chi_sets = []
    for s in structure.get('sets', []):
        if s['type'] == 'chi':
            chi_sets.append(s)
    for m in melds:
        if m['type'] == 'chow':
            chi_sets.append({'type': 'chi', 'tiles': m['tiles']})
    
    # 按起始数字分组
    by_num = {}
    for c in chi_sets:
        tiles = c.get('tiles', [])
        if tiles:
            num = get_tile_number(tiles[0])
            suit = get_tile_suit(tiles[0])
            if num not in by_num:
                by_num[num] = set()
            by_num[num].add(suit)
    
    # 检查是否有某个数字三种花色都有
    return any(len(suits) >= 3 for suits in by_num.values())


def check_ikkitsuukan(structure, melds):
    """检查一气通贯: 同花色123+456+789"""
    chi_sets = []
    for s in structure.get('sets', []):
        if s['type'] == 'chi':
            chi_sets.append(s)
    for m in melds:
        if m['type'] == 'chow':
            chi_sets.append({'type': 'chi', 'tiles': m['tiles']})
    
    # 按花色分组
    by_suit = {'wan': set(), 'tiao': set(), 'tong': set()}
    for c in chi_sets:
        tiles = c.get('tiles', [])
        if tiles:
            num = get_tile_number(tiles[0])
            suit = get_tile_suit(tiles[0])
            if suit in by_suit:
                by_suit[suit].add(num)
    
    # 检查是否有花色包含1,4,7
    return any({1, 4, 7}.issubset(nums) for nums in by_suit.values())


def check_chanta(structure, melds):
    """检查混全带幺九: 每组都包含幺九牌，且有字牌"""
    if structure.get('type') != 'standard':
        return False
    
    has_honor = False
    all_sets = structure.get('sets', [])
    
    # 检查雀头
    pair = structure['pair']
    if not is_yaojiu(pair):
        return False
    if is_honor_tile(pair):
        has_honor = True
    
    # 检查面子
    for s in all_sets:
        if s['type'] == 'pon':
            if not is_yaojiu(s['tile']):
                return False
            if is_honor_tile(s['tile']):
                has_honor = True
        elif s['type'] == 'chi':
            # 顺子必须包含1或9
            tiles = s.get('tiles', [])
            if not any(get_tile_number(t) in (1, 9) for t in tiles):
                return False
    
    for m in melds:
        tiles = m.get('tiles', [])
        if not any(is_yaojiu(normalize_tile(t)) for t in tiles):
            return False
        if any(is_honor_tile(normalize_tile(t)) for t in tiles):
            has_honor = True
    
    return has_honor


def check_junchan(structure, melds):
    """检查纯全带幺九: 每组都包含老头牌（1或9），无字牌"""
    if structure.get('type') != 'standard':
        return False
    
    # 检查雀头
    pair = structure['pair']
    if not is_terminal(pair):
        return False
    
    # 检查面子
    for s in structure.get('sets', []):
        if s['type'] == 'pon':
            if not is_terminal(s['tile']):
                return False
        elif s['type'] == 'chi':
            tiles = s.get('tiles', [])
            if not any(get_tile_number(t) in (1, 9) for t in tiles):
                return False
    
    for m in melds:
        tiles = m.get('tiles', [])
        if not any(is_terminal(normalize_tile(t)) for t in tiles):
            return False
    
    return True


def check_toitoi(structure, melds):
    """检查对对和: 4个刻子"""
    if structure.get('type') != 'standard':
        return False
    
    pon_count = sum(1 for s in structure.get('sets', []) if s['type'] == 'pon')
    pon_count += sum(1 for m in melds if m['type'] in ('pong', 'kong', 'concealed_kong'))
    
    return pon_count >= 4


def check_sanankou(structure, melds, is_tsumo, win_tile):
    """检查三暗刻: 3个暗刻"""
    if structure.get('type') != 'standard':
        return False
    
    ankou_count = 0
    
    # 手牌中的刻子都是暗刻（除非和牌的那张组成的刻子且是荣和）
    for s in structure.get('sets', []):
        if s['type'] == 'pon':
            # 如果是荣和且刻子包含和牌，则不算暗刻
            if not is_tsumo and s['tile'] == normalize_tile(win_tile):
                continue
            ankou_count += 1
    
    # 暗杠也算暗刻
    for m in melds:
        if m['type'] == 'concealed_kong':
            ankou_count += 1
    
    return ankou_count >= 3


def check_sankantsu(melds):
    """检查三杠子: 3个杠子"""
    kong_count = sum(1 for m in melds if m['type'] in ('kong', 'concealed_kong'))
    return kong_count >= 3


def check_suukantsu(melds):
    """检查四杠子: 4个杠子（役满）"""
    kong_count = sum(1 for m in melds if m['type'] in ('kong', 'concealed_kong'))
    return kong_count >= 4


def check_shousangen(structure, melds):
    """检查小三元: 两组三元牌刻子 + 一组三元牌雀头"""
    if structure.get('type') != 'standard':
        return False
    
    sangen = ['中', '发', '白']
    sangen_pon = 0
    sangen_pair = False
    
    # 检查手牌中的刻子和雀头
    for s in structure.get('sets', []):
        if s['type'] == 'pon' and s['tile'] in sangen:
            sangen_pon += 1
    
    pair = structure.get('pair')
    if pair and pair in sangen:
        sangen_pair = True
    
    # 检查副露中的三元牌刻子
    for m in melds:
        if m['type'] in ('pong', 'kong', 'concealed_kong'):
            tile = normalize_tile(m['tiles'][0])
            if tile in sangen:
                sangen_pon += 1
    
    return sangen_pon == 2 and sangen_pair


def check_sanshoku_doukou(structure, melds):
    """检查三色同刻: 万条筒各有相同数字的刻子"""
    if structure.get('type') != 'standard':
        return False
    
    # 收集所有刻子
    pons = {}  # {数字: [花色列表]}
    
    for s in structure.get('sets', []):
        if s['type'] == 'pon':
            tile = s['tile']
            if is_number_tile(tile):
                num = get_tile_number(tile)
                suit = get_tile_suit(tile)
                if num not in pons:
                    pons[num] = []
                pons[num].append(suit)
    
    for m in melds:
        if m['type'] in ('pong', 'kong', 'concealed_kong'):
            tile = normalize_tile(m['tiles'][0])
            if is_number_tile(tile):
                num = get_tile_number(tile)
                suit = get_tile_suit(tile)
                if num not in pons:
                    pons[num] = []
                pons[num].append(suit)
    
    # 检查是否有某个数字在三种花色都有刻子
    for num, suits in pons.items():
        if len(set(suits)) >= 3:
            return True
    
    return False


def check_honroutou(hand, melds):
    """检查混老头: 全是幺九牌（老头牌+字牌），只有刻子和雀头"""
    all_tiles = hand.copy()
    for m in melds:
        all_tiles.extend([normalize_tile(t) for t in m.get('tiles', [])])
    
    has_terminal = False
    has_honor = False
    
    for t in all_tiles:
        t = normalize_tile(t)
        if is_terminal(t):
            has_terminal = True
        elif is_honor_tile(t):
            has_honor = True
        else:
            return False  # 有非幺九牌
    
    # 必须同时有老头牌和字牌
    return has_terminal and has_honor


def check_honitsu(hand, melds):
    """检查混一色: 一种花色+字牌"""
    all_tiles = hand.copy()
    for m in melds:
        all_tiles.extend([normalize_tile(t) for t in m.get('tiles', [])])
    
    suits = set()
    has_honor = False
    for t in all_tiles:
        t = normalize_tile(t)
        suit = get_tile_suit(t)
        if suit == 'zi':
            has_honor = True
        else:
            suits.add(suit)
    
    return has_honor and len(suits) == 1


def check_chinitsu(hand, melds):
    """检查清一色: 只有一种花色（无字牌）"""
    all_tiles = hand.copy()
    for m in melds:
        all_tiles.extend([normalize_tile(t) for t in m.get('tiles', [])])
    
    suits = set()
    for t in all_tiles:
        t = normalize_tile(t)
        suit = get_tile_suit(t)
        if suit == 'zi':
            return False
        suits.add(suit)
    
    return len(suits) == 1


# ========== 役满检查 ==========

def check_suuankou(structure, melds, is_tsumo, win_tile):
    """检查四暗刻: 4个暗刻"""
    if structure.get('type') != 'standard':
        return False
    
    # 不能有明副露（暗杠除外）
    for m in melds:
        if m['type'] not in ('concealed_kong',):
            return False
    
    ankou_count = 0
    for s in structure.get('sets', []):
        if s['type'] == 'pon':
            if not is_tsumo and s['tile'] == normalize_tile(win_tile):
                continue
            ankou_count += 1
    
    for m in melds:
        if m['type'] == 'concealed_kong':
            ankou_count += 1
    
    return ankou_count >= 4


def check_daisangen(structure, melds):
    """检查大三元: 中发白都是刻子"""
    pon_tiles = set()
    for s in structure.get('sets', []):
        if s['type'] == 'pon':
            pon_tiles.add(s['tile'])
    for m in melds:
        if m['type'] in ('pong', 'kong', 'concealed_kong'):
            pon_tiles.add(normalize_tile(m['tiles'][0]))
    
    return set(SANGENPAI).issubset(pon_tiles)


def check_suushii(structure, melds):
    """检查四喜: 返回 (小四喜, 大四喜)"""
    pon_tiles = set()
    for s in structure.get('sets', []):
        if s['type'] == 'pon':
            pon_tiles.add(s['tile'])
    for m in melds:
        if m['type'] in ('pong', 'kong', 'concealed_kong'):
            pon_tiles.add(normalize_tile(m['tiles'][0]))
    
    kaze_pons = set(KAZEHAI) & pon_tiles
    pair = structure.get('pair', '')
    
    if len(kaze_pons) == 4:
        return False, True  # 大四喜
    elif len(kaze_pons) == 3 and pair in KAZEHAI:
        return True, False  # 小四喜
    return False, False


def check_tsuuiisou(hand, melds):
    """检查字一色: 全是字牌"""
    all_tiles = hand.copy()
    for m in melds:
        all_tiles.extend([normalize_tile(t) for t in m.get('tiles', [])])
    
    return all(is_honor_tile(normalize_tile(t)) for t in all_tiles)


def check_chinroutou(hand, melds):
    """检查清老头: 全是老头牌（1和9）"""
    all_tiles = hand.copy()
    for m in melds:
        all_tiles.extend([normalize_tile(t) for t in m.get('tiles', [])])
    
    return all(is_terminal(normalize_tile(t)) for t in all_tiles)


def check_ryuuiisou(hand, melds):
    """检查绿一色: 只有绿色牌（23468条+发）"""
    all_tiles = hand.copy()
    for m in melds:
        all_tiles.extend(m.get('tiles', []))
    
    return all(normalize_tile(t) in GREEN_TILES for t in all_tiles)


def check_chuurenpoutou(hand, is_menzen):
    """检查九莲宝灯: 1112345678999 + 任意同花色"""
    if not is_menzen:
        return False
    if len(hand) != 14:
        return False
    
    # 检查是否是同一花色
    suits = set(get_tile_suit(t) for t in hand)
    if len(suits) != 1 or 'zi' in suits:
        return False
    
    suit = list(suits)[0]
    
    # 统计数量
    counts = [0] * 10  # counts[1] ~ counts[9]
    for t in hand:
        num = get_tile_number(t)
        counts[num] += 1
    
    # 检查 1112345678999 的结构
    # 需要: 1>=3, 2>=1, 3>=1, 4>=1, 5>=1, 6>=1, 7>=1, 8>=1, 9>=3
    if counts[1] < 3 or counts[9] < 3:
        return False
    for i in range(2, 9):
        if counts[i] < 1:
            return False
    
    return True


# ========== 符数计算 ==========

def calculate_fu(structure, melds, win_tile, is_tsumo, is_menzen, player_wind, round_wind):
    """
    计算符数
    
    基本符: 20符（七对子固定25符）
    """
    if structure.get('type') == 'chitoitsu':
        return 25  # 七对子固定25符
    
    fu = 20  # 基本符
    
    # 门清荣和 +10符
    if is_menzen and not is_tsumo:
        fu += 10
    
    # 自摸 +2符（平和自摸除外）
    if is_tsumo:
        fu += 2
    
    # 雀头
    pair = structure.get('pair', '')
    if pair in SANGENPAI:
        fu += 2
    if pair == player_wind:
        fu += 2
    if pair == round_wind:
        fu += 2
    
    # 面子
    for s in structure.get('sets', []):
        if s['type'] == 'pon':
            tile = s['tile']
            base = 4 if is_yaojiu(tile) else 2
            # 手牌中的刻子是暗刻 x2
            fu += base * 2
    
    for m in melds:
        tiles = m.get('tiles', [])
        if not tiles:
            continue
        tile = normalize_tile(tiles[0])
        
        if m['type'] == 'pong':
            base = 4 if is_yaojiu(tile) else 2
            fu += base  # 明刻
        elif m['type'] == 'kong':
            base = 16 if is_yaojiu(tile) else 8
            fu += base  # 明杠
        elif m['type'] == 'concealed_kong':
            base = 32 if is_yaojiu(tile) else 16
            fu += base  # 暗杠
    
    # 听牌形状（简化处理，边张/嵌张/单骑 +2符）
    # TODO: 更精确的听牌判断
    
    # 向上取整到10的倍数
    fu = ((fu + 9) // 10) * 10
    
    return max(fu, 30)  # 最少30符（除了平和自摸20符）


# ========== 点数计算 ==========

def calculate_score(han, fu, is_dealer, is_tsumo):
    """
    计算点数
    
    Args:
        han: 番数
        fu: 符数
        is_dealer: 是否庄家
        is_tsumo: 是否自摸
        
    Returns:
        dict: {'total': 总点数, 'from_dealer': 从庄家获得, 'from_non_dealer': 从闲家获得}
    """
    if han >= 13:
        base = 8000  # 累计役满
    elif han >= 11:
        base = 6000  # 三倍满
    elif han >= 8:
        base = 4000  # 倍满
    elif han >= 6:
        base = 3000  # 跳满
    elif han >= 5 or (han >= 4 and fu >= 40) or (han >= 3 and fu >= 70):
        base = 2000  # 满贯
    else:
        # 基本点 = 符 × 2^(番+2)
        base = fu * (2 ** (han + 2))
        base = min(base, 2000)  # 上限满贯
    
    if is_dealer:
        if is_tsumo:
            # 庄家自摸：每家付 base × 2（向上取整百）
            each = _round_up_100(base * 2)
            return {'total': each * 3, 'from_non_dealer': each}
        else:
            # 庄家荣和：放铳者付 base × 6
            total = _round_up_100(base * 6)
            return {'total': total}
    else:
        if is_tsumo:
            # 闲家自摸：庄家付 base × 2，其他闲家付 base × 1
            from_dealer = _round_up_100(base * 2)
            from_non_dealer = _round_up_100(base)
            return {
                'total': from_dealer + from_non_dealer * 2,
                'from_dealer': from_dealer,
                'from_non_dealer': from_non_dealer
            }
        else:
            # 闲家荣和：放铳者付 base × 4
            total = _round_up_100(base * 4)
            return {'total': total}


def _round_up_100(n):
    """向上取整到100的倍数"""
    return ((n + 99) // 100) * 100
