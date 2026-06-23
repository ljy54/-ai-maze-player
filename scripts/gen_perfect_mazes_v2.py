"""生成完美迷宫v2：优化S/E/B/G/T放置，确保贪心算法可达金币"""
import json, os, random
from collections import deque

DATA_DIR = 'data'
random.seed(123)

DIRS = [(-2, 0, -1, 0), (2, 0, 1, 0), (0, -2, 0, -1), (0, 2, 0, 1)]


def generate_perfect_maze(rows, cols):
    """递归回溯(DFS)生成完美迷宫"""
    if rows % 2 == 0: rows -= 1
    if cols % 2 == 0: cols -= 1
    maze = [['#' for _ in range(cols)] for _ in range(rows)]
    stack = [(1, 1)]
    maze[1][1] = ' '
    while stack:
        r, c = stack[-1]
        dirs = list(DIRS); random.shuffle(dirs)
        carved = False
        for dr2, dc2, dr1, dc1 in dirs:
            nr, nc = r + dr2, c + dc2
            if 0 < nr < rows and 0 < nc < cols and maze[nr][nc] == '#':
                maze[r + dr1][c + dc1] = ' '
                maze[nr][nc] = ' '
                stack.append((nr, nc))
                carved = True
                break
        if not carved:
            stack.pop()
    return maze


def get_passable(maze):
    return [(r, c) for r, row in enumerate(maze) for c, ch in enumerate(row) if ch != '#']


def get_neighbors(maze, r, c):
    rows, cols = len(maze), len(maze[0])
    nb = []
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols and maze[nr][nc] != '#':
            nb.append((nr, nc))
    return nb


def bfs_path(maze, start, end):
    rows, cols = len(maze), len(maze[0])
    prev = {start: None}
    q = deque([start])
    while q:
        r, c = q.popleft()
        if (r, c) == end: break
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if (0 <= nr < rows and 0 <= nc < cols and
                    maze[nr][nc] != '#' and (nr, nc) not in prev):
                prev[(nr, nc)] = (r, c)
                q.append((nr, nc))
    if end not in prev: return []
    path = [end]
    while path[-1] != start:
        path.append(prev[path[-1]])
    path.reverse()
    return path


def bfs_distance(maze, start):
    rows, cols = len(maze), len(maze[0])
    dist = {start: 0}
    q = deque([start])
    while q:
        r, c = q.popleft()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if (0 <= nr < rows and 0 <= nc < cols and
                    maze[nr][nc] != '#' and (nr, nc) not in dist):
                dist[(nr, nc)] = dist[(r, c)] + 1
                q.append((nr, nc))
    return dist


def check_perfect_maze(maze):
    rows, cols = len(maze), len(maze[0])
    V = 0; E = 0; start = None
    for r in range(rows):
        for c in range(cols):
            if maze[r][c] != '#':
                V += 1
                if start is None: start = (r, c)
                if r + 1 < rows and maze[r + 1][c] != '#': E += 1
                if c + 1 < cols and maze[r][c + 1] != '#': E += 1
    if start is None: return False, V, E
    dist = bfs_distance(maze, start)
    return (len(dist) == V and E == V - 1), V, E


def print_maze(maze):
    for r, row in enumerate(maze):
        line = ''
        for c, ch in enumerate(row):
            line += '·' if ch == ' ' else ch
        print(f'  {r:2d} {line}')


def place_entities(maze, seed_offset):
    """在完美迷宫上放置S/E/B/G/T，优化贪心可达性"""
    random.seed(123 + seed_offset)
    passable = get_passable(maze)

    # 1. S：选有≥2个可通行邻居的位置（避免关在陷阱走廊）
    good_s = [p for p in passable if len(get_neighbors(maze, p[0], p[1])) >= 2]
    s_pos = random.choice(good_s)

    # 2. E：选离S最远的角落
    dist_s = bfs_distance(maze, s_pos)
    far = sorted([(p, d) for p, d in dist_s.items()], key=lambda x: -x[1])
    e_pos = far[0][0]

    # 3. B：放在S→E路径的前2/3处（保证B后有足够空间到E）
    path_s_e = bfs_path(maze, s_pos, e_pos)
    b_idx = len(path_s_e) * 2 // 3
    b_pos = path_s_e[b_idx]

    # 收集主路径集合
    path_s_b = bfs_path(maze, s_pos, b_pos)
    path_b_e = bfs_path(maze, b_pos, e_pos)
    main_path = set(path_s_e)
    s_b_path = set(path_s_b)
    b_e_path = set(path_b_e)

    maze[s_pos[0]][s_pos[1]] = 'S'
    maze[e_pos[0]][e_pos[1]] = 'E'
    maze[b_pos[0]][b_pos[1]] = 'B'
    used = {s_pos, e_pos, b_pos}

    # 4. 金币：优先放在S→B路径附近的分支上（贪心容易发现）
    #    找距离S→B主路径距离≥1且≤3的可通行格（在侧支但不太远）
    gold_candidates = []
    for p in passable:
        if p in used: continue
        if p in main_path: continue  # 不放在主路径上（太容易）
        # 计算到S→B路径的距离
        min_dist = min(abs(p[0]-mp[0]) + abs(p[1]-mp[1]) for mp in s_b_path)
        if 1 <= min_dist <= 4:
            gold_candidates.append((p, min_dist))

    # 按距离排序，优先放近的（贪心用小视野容易发现）
    gold_candidates.sort(key=lambda x: x[1])
    gold_count = min(6, len(gold_candidates))
    for i in range(gold_count):
        p, _ = gold_candidates[i]
        maze[p[0]][p[1]] = 'G'
        used.add(p)

    # 5. 陷阱：放在B→E路径的支路上（不是必经，但探索可能触发）
    trap_candidates = []
    for p in passable:
        if p in used: continue
        if p in main_path: continue
        # 到B→E路径的距离≥2的侧支
        min_dist = min(abs(p[0]-mp[0]) + abs(p[1]-mp[1]) for mp in b_e_path)
        if 2 <= min_dist <= 5:
            trap_candidates.append(p)

    random.shuffle(trap_candidates)
    trap_count = min(3, len(trap_candidates))
    for i in range(trap_count):
        p = trap_candidates[i]
        maze[p[0]][p[1]] = 'T'
        used.add(p)

    # 6. 补充1-2个陷阱在S→B附近（增加挑战，但不是在S的必经方向上）
    extra_trap_candidates = []
    for p in passable:
        if p in used: continue
        if p in s_b_path: continue
        if p in main_path: continue
        # 离S至少4步
        if p in dist_s and dist_s[p] >= 4:
            nb = get_neighbors(maze, p[0], p[1])
            # 不在S的唯一出口方向上
            s_nb = get_neighbors(maze, s_pos[0], s_pos[1])
            if len(s_nb) >= 2 and p not in s_nb:
                extra_trap_candidates.append(p)

    random.shuffle(extra_trap_candidates)
    for i in range(min(2, len(extra_trap_candidates))):
        p = extra_trap_candidates[i]
        maze[p[0]][p[1]] = 'T'
        used.add(p)

    return s_pos, e_pos, b_pos


# ============================================================
# 生成5个迷宫，验证每个确保S有≥2个出口
# ============================================================
boss_configs = [
    ([12, 10, 8],  [[7, 4], [4, 2], [3, 1]],         18, 4),
    ([15, 12],     [[8, 5], [5, 2], [4, 3]],          20, 5),
    ([20, 16, 12], [[10, 4], [6, 3], [4, 2], [3, 1]], 22, 4),
    ([18, 14, 10], [[9, 5], [5, 3], [4, 2]],          20, 3),
    ([14, 12, 10, 8], [[8, 4], [3, 2], [4, 2], [5, 3]], 20, 5),
]

names = [
    ('maze_pf_v2_01', 'v2-迷宫01'),
    ('maze_pf_v2_02', 'v2-迷宫02'),
    ('maze_pf_v2_03', 'v2-迷宫03'),
    ('maze_pf_v2_04', 'v2-迷宫04'),
    ('maze_pf_v2_05', 'v2-迷宫05'),
]

for idx in range(5):
    maze = generate_perfect_maze(15, 15)
    s, e, b = place_entities(maze, seed_offset=idx * 10)

    perfect, V, E = check_perfect_maze(maze)
    golds = sum(1 for r in maze for c in r if c == 'G')
    traps = sum(1 for r in maze for c in r if c == 'T')
    s_nb = len(get_neighbors(maze, s[0], s[1]))

    B, skills, minR, coin = boss_configs[idx]
    data = {
        'maze': maze, 'B': B, 'PlayerSkills': skills,
        'minRouds': minR, 'CoinConsumption': coin
    }

    fname = names[idx][0]
    fpath = os.path.join(DATA_DIR, fname + '.json')
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

    label = names[idx][1]
    status = 'OK' if perfect else 'FAIL'
    print(f'[{label}] {status} V={V} E={E} | '
          f'S={s}(出口{s_nb}) E={e} B={b} | 金币{golds} 陷阱{traps}')
    print_maze(maze)
    print()

print('=== v2完美迷宫生成完毕 ===')
