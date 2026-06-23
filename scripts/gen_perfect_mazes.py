"""生成符合设计组要求的完美迷宫（树结构，无回路，唯一通路）"""
import json, os, random
from collections import deque

DATA_DIR = 'data'
random.seed(42)

DIRS = [(-2, 0, -1, 0), (2, 0, 1, 0), (0, -2, 0, -1), (0, 2, 0, 1)]


def generate_perfect_maze(rows, cols):
    """递归回溯(DFS)生成完美迷宫：初始全墙，从起点挖通"""
    # 确保行列是奇数（标准迷宫生成要求）
    if rows % 2 == 0:
        rows -= 1
    if cols % 2 == 0:
        cols -= 1

    # 全墙初始化
    maze = [['#' for _ in range(cols)] for _ in range(rows)]

    # 从 (1,1) 开始 DFS 挖路
    stack = [(1, 1)]
    maze[1][1] = ' '

    while stack:
        r, c = stack[-1]
        # 随机打乱方向
        dirs = list(DIRS)
        random.shuffle(dirs)
        carved = False
        for dr2, dc2, dr1, dc1 in dirs:
            nr, nc = r + dr2, c + dc2
            if 0 < nr < rows and 0 < nc < cols and maze[nr][nc] == '#':
                # 打通中间格和目标格
                maze[r + dr1][c + dc1] = ' '
                maze[nr][nc] = ' '
                stack.append((nr, nc))
                carved = True
                break
        if not carved:
            stack.pop()

    return maze


def get_passable_positions(maze):
    """获取所有可通行格子的坐标列表"""
    positions = []
    for r, row in enumerate(maze):
        for c, ch in enumerate(row):
            if ch != '#':
                positions.append((r, c))
    return positions


def bfs_distance(maze, start):
    """从start出发到所有可通行格子的BFS距离"""
    rows, cols = len(maze), len(maze[0])
    dist = {}
    q = deque([(start[0], start[1], 0)])
    visited = {start}
    while q:
        r, c, d = q.popleft()
        dist[(r, c)] = d
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if (0 <= nr < rows and 0 <= nc < cols and
                    maze[nr][nc] != '#' and (nr, nc) not in visited):
                visited.add((nr, nc))
                q.append((nr, nc, d + 1))
    return dist


def bfs_path(maze, start, end):
    """BFS最短路径"""
    rows, cols = len(maze), len(maze[0])
    prev = {start: None}
    q = deque([start])
    while q:
        r, c = q.popleft()
        if (r, c) == end:
            break
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if (0 <= nr < rows and 0 <= nc < cols and
                    maze[nr][nc] != '#' and (nr, nc) not in prev):
                prev[(nr, nc)] = (r, c)
                q.append((nr, nc))

    if end not in prev:
        return []
    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path


def check_perfect_maze(maze):
    """验证完美迷宫：连通 + 唯一通路（边数=V-1）"""
    rows, cols = len(maze), len(maze[0])
    V = 0  # 可通行格子数
    E = 0  # 相邻可通行对（每条边只计一次：右下方向）
    start = None

    for r in range(rows):
        for c in range(cols):
            if maze[r][c] != '#':
                V += 1
                if start is None:
                    start = (r, c)
                # 只检查右和下（避免重复计数）
                if r + 1 < rows and maze[r + 1][c] != '#':
                    E += 1
                if c + 1 < cols and maze[r][c + 1] != '#':
                    E += 1

    # 检查连通性
    if start is None:
        return False, V, E, "无可行走格子"
    dist = bfs_distance(maze, start)
    if len(dist) != V:
        return False, V, E, f"不连通: 可到达{len(dist)}/{V}格"

    # 检查唯一通路
    if E != V - 1:
        return False, V, E, f"存在回路: V={V}, E={E}, 应为E=V-1={V-1}"

    return True, V, E, "完美迷宫✓"


def place_resource(maze, ch, positions_used, avoid_near):
    """放置资源（避免重复和过于靠近）"""
    passable = get_passable_positions(maze)
    # 过滤掉已用的和需要避开的
    candidates = [p for p in passable
                  if p not in positions_used
                  and all(abs(p[0] - a[0]) + abs(p[1] - a[1]) >= 3
                          for a in avoid_near)]
    if not candidates:
        # 放宽条件
        candidates = [p for p in passable if p not in positions_used]
    if not candidates:
        return None
    return random.choice(candidates)


def print_maze(maze):
    for r, row in enumerate(maze):
        line = ''
        for c, ch in enumerate(row):
            line += '·' if ch == ' ' else ch
        print(f'  {r:2d} {line}')


# ============================================================
# 生成 5 个完美迷宫
# ============================================================
maze_configs = []

for i in range(5):
    # 生成 15×15 完美迷宫 (保证奇数尺寸)
    maze = generate_perfect_maze(15, 15)

    # 在可通行格子上放置 S, E, B, G, T
    passable = get_passable_positions(maze)
    used = set()

    # S: 选最远的几个角落之一
    corners = [(1, 1), (1, 13), (13, 1), (13, 13)]
    valid_corners = [c for c in corners if c in passable]
    s_pos = valid_corners[0]
    maze[s_pos[0]][s_pos[1]] = 'S'
    used.add(s_pos)

    # E: 选对面角落
    if s_pos == (1, 1):
        e_candidates = [(13, 13)]
    elif s_pos == (1, 13):
        e_candidates = [(13, 1)]
    elif s_pos == (13, 1):
        e_candidates = [(1, 13)]
    else:
        e_candidates = [(1, 1)]

    # E必须在S可到达的远处
    dist_from_s = bfs_distance(maze, s_pos)
    far_positions = sorted(
        [(p, d) for p, d in dist_from_s.items() if p not in used],
        key=lambda x: -x[1]
    )
    e_pos = far_positions[0][0]
    maze[e_pos[0]][e_pos[1]] = 'E'
    used.add(e_pos)

    # B: 放在 S→E 路径的中途（离E近一些）
    path_s_e = bfs_path(maze, s_pos, e_pos)
    # 在路径中点附近找Boss位置
    b_idx = len(path_s_e) * 3 // 4  # 离E近
    b_pos = path_s_e[b_idx]
    # 确保B不在S或E上
    while b_pos in used and b_idx < len(path_s_e) - 1:
        b_idx += 1
        b_pos = path_s_e[b_idx]
    maze[b_pos[0]][b_pos[1]] = 'B'
    used.add(b_pos)

    # 金币: 在S→B和B→E路径分支上放置
    path_s_b = bfs_path(maze, s_pos, b_pos)
    path_b_e = bfs_path(maze, b_pos, e_pos)

    # 找不在主路径上的分支点放金币（让AI需要偏离主路）
    gold_count = 0
    target_golds = 5 + i  # 5~9个金币

    # 先收集所有可通行格子到主路径的距离
    main_path_set = set(path_s_e)
    branch_candidates = []
    for p in passable:
        if p not in used and p not in main_path_set:
            # 计算到主路径的最短距离
            min_dist = min(abs(p[0] - mp[0]) + abs(p[1] - mp[1])
                           for mp in main_path_set)
            branch_candidates.append((p, min_dist))

    # 按距离排序，选较远的（放在分支深处）
    branch_candidates.sort(key=lambda x: -x[1])

    for p, _ in branch_candidates:
        if gold_count >= target_golds:
            break
        if p in used:
            continue
        maze[p[0]][p[1]] = 'G'
        used.add(p)
        gold_count += 1

    # 如果金币不够，在主路径附近也放
    if gold_count < 4:
        for p in passable:
            if gold_count >= 4:
                break
            if p not in used and p not in main_path_set:
                maze[p[0]][p[1]] = 'G'
                used.add(p)
                gold_count += 1

    # 陷阱: 放在主路径的支路入口处，迫使AI走支路
    trap_count = 0
    target_traps = 3 + i // 2  # 3~5个陷阱

    # 陷阱放在主路径上（必经），形成"过路费"
    # 但完美迷宫中每个分叉都是唯一通路，陷阱放分支入口才有意义
    for p in passable:
        if trap_count >= target_traps:
            break
        if p in used:
            continue
        # 放在主路径附近但不是金币位置
        if p in main_path_set:
            maze[p[0]][p[1]] = 'T'
            used.add(p)
            trap_count += 1

    # 如果陷阱不够，在分支上补
    for p in passable:
        if trap_count >= target_traps:
            break
        if p not in used:
            maze[p[0]][p[1]] = 'T'
            used.add(p)
            trap_count += 1

    maze_configs.append((maze, gold_count, trap_count, s_pos, e_pos, b_pos))

# ============================================================
# 验证并保存
# ============================================================
names = [
    ('maze_perfect_01', '完美迷宫01-深度分支'),
    ('maze_perfect_02', '完美迷宫02-长走廊'),
    ('maze_perfect_03', '完美迷宫03-螺旋'),
    ('maze_perfect_04', '完美迷宫04-多岔路'),
    ('maze_perfect_05', '完美迷宫05-曲折'),
]

# 不同的Boss和技能配置
boss_configs = [
    ([12, 10, 8], [[7, 4], [4, 2], [3, 1]], 18, 4),
    ([15, 12], [[8, 5], [5, 2], [4, 3]], 20, 5),
    ([20, 16, 12], [[10, 4], [6, 3], [4, 2], [3, 1]], 22, 4),
    ([18, 14, 10], [[9, 5], [5, 3], [4, 2]], 20, 3),
    ([14, 12, 10, 8], [[8, 4], [3, 2], [4, 2], [5, 3]], 20, 5),
]

for idx, ((fname, label), (maze, g, t, s, e, b)) in enumerate(
        zip(names, maze_configs)):
    B, skills, minR, coin = boss_configs[idx]

    # 验证
    is_perfect, V, E, msg = check_perfect_maze(maze)
    if not is_perfect:
        print(f'[{label}] 验证失败: {msg}')
        continue

    # 验证关键点连通
    errors = []
    for ch, pt in [('S', s), ('E', e), ('B', b)]:
        if pt is None:
            errors.append(f'缺少{ch}')
    if errors:
        print(f'[{label}] 验证失败: {errors}')
        continue

    data = {
        'maze': maze,
        'B': B,
        'PlayerSkills': skills,
        'minRouds': minR,
        'CoinConsumption': coin
    }

    fpath = os.path.join(DATA_DIR, fname + '.json')
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

    print(f'[{label}] OK: {fname}.json')
    print(f'  V={V} E={E} E-V+1={E-V+1} | 金币:{g} 陷阱:{t}')
    print(f'  S={s} E={e} B={b}')
    print_maze(maze)
    print()

print('=== 5个完美迷宫生成完毕 ===')
