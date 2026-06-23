"""生成复活功能测试迷宫：Boss HP高、minRounds低、路径上有足够金币"""
import json, os, random
from collections import deque

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
random.seed(999)

DIRS = [(-2, 0, -1, 0), (2, 0, 1, 0), (0, -2, 0, -1), (0, 2, 0, 1)]


def generate_perfect_maze(rows, cols):
    """DFS生成完美迷宫"""
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


def print_maze(maze):
    for r, row in enumerate(maze):
        line = ''
        for c, ch in enumerate(row):
            line += '·' if ch == ' ' else ch
        print(f'  {r:2d} {line}')


# ============================================================
# 生成复活测试迷宫
# ============================================================
maze = generate_perfect_maze(15, 15)
passable = get_passable(maze)

# S：选边缘位置
good_s = [p for p in passable if len(get_neighbors(maze, p[0], p[1])) >= 2]
s_pos = random.choice(good_s)

# E：选离S最远的位置
dist_s = bfs_distance(maze, s_pos)
far = sorted([(p, d) for p, d in dist_s.items()], key=lambda x: -x[1])
e_pos = far[0][0]

# B：放在S→E路径中间偏后位置（给B→E留空间）
path_s_e = bfs_path(maze, s_pos, e_pos)
b_idx = len(path_s_e) * 3 // 5
b_pos = path_s_e[b_idx]

maze[s_pos[0]][s_pos[1]] = 'S'
maze[e_pos[0]][e_pos[1]] = 'E'
maze[b_pos[0]][b_pos[1]] = 'B'
used = {s_pos, e_pos, b_pos}

# 金币全部放在S→B主路径上（保证贪心一定能吃到足够金币付复活费）
path_s_b = bfs_path(maze, s_pos, b_pos)
main_set = set(path_s_b) | set(bfs_path(maze, b_pos, e_pos))

# 在主路径上放5个金币（=250金币）
gold_positions = []
for p in path_s_b:
    if p in used: continue
    if len(gold_positions) >= 5: break
    maze[p[0]][p[1]] = 'G'
    gold_positions.append(p)
    used.add(p)

# 在S→B主路径上放1个陷阱（= -30，确保有陷阱但金币够复活）
for p in path_s_b:
    if p in used: continue
    maze[p[0]][p[1]] = 'T'
    used.add(p)
    break

# 在B→E的支路上放2个陷阱（不在主路径上）
b_e_path = bfs_path(maze, b_pos, e_pos)
side_traps = 0
for p in passable:
    if p in used: continue
    if p in b_e_path: continue
    if side_traps >= 2: break
    maze[p[0]][p[1]] = 'T'
    used.add(p)
    side_traps += 1

# Boss配置：2个Boss总HP=80，技能[[8,4],[2,0],[4,2],[6,3]]每回合最优约5DPS
# 约需14回合击败，minRounds=10 → 超出4回合
# revival_cost = 4 * 8 = 32金币
# 路径上5金币=250 - 1陷阱=30 → net = 220 > 32 ✓ 可复活
data = {
    'maze': maze,
    'B': [45, 35],                    # 总HP=80，2个Boss
    'PlayerSkills': [[8, 4], [2, 0], [4, 2], [6, 3]],
    'minRouds': 10,                   # 给10回合（实际需要~14）
    'CoinConsumption': 8,             # 每额外回合消耗8金币
}

fpath = os.path.join(DATA_DIR, 'maze_revival_test.json')
with open(fpath, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 打印汇总
golds = sum(1 for r in maze for c in r if c == 'G')
traps = sum(1 for r in maze for c in r if c == 'T')
print(f'复活测试迷宫已生成: {fpath}')
print(f'S={s_pos} E={e_pos} B={b_pos}')
print(f'金币:{golds}个(={golds*50}金币)  陷阱:{traps}个')
print(f'BossHP: {"+".join(str(h) for h in data["B"])}={sum(data["B"])}')
print(f'minRounds={data["minRouds"]}  CoinConsumption={data["CoinConsumption"]}')
print(f'预期: 需要约14回合击败Boss, 超出4回合, 复活费=32金币')
print(f'      路径净收益约220 >= 32, 可以复活')
print()
print_maze(maze)
