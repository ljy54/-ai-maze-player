"""生成5个不同特征的15×15测试迷宫"""
import json, os
from collections import deque

DATA_DIR = 'data'


def bfs_path(maze, start, end):
    """验证两点是否连通"""
    rows, cols = len(maze), len(maze[0])
    q = deque([start])
    visited = {start}
    while q:
        r, c = q.popleft()
        if (r, c) == end:
            return True
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if (0 <= nr < rows and 0 <= nc < cols and
                    maze[nr][nc] != '#' and (nr, nc) not in visited):
                visited.add((nr, nc))
                q.append((nr, nc))
    return False


def find_pos(maze, ch):
    for r, row in enumerate(maze):
        for c, cell in enumerate(row):
            if cell == ch:
                return (r, c)
    return (-1, -1)


def count_ch(maze, ch):
    return sum(1 for row in maze for c in row if c == ch)


def validate_maze(maze):
    """验证迷宫关键点全部连通"""
    errors = []
    s = find_pos(maze, 'S')
    e = find_pos(maze, 'E')
    b = find_pos(maze, 'B')
    if s == (-1, -1): errors.append('缺少起点S')
    if e == (-1, -1): errors.append('缺少终点E')
    if b == (-1, -1): errors.append('缺少Boss B')
    if errors:
        return errors

    for label, pt in [('E', e), ('B', b)]:
        if not bfs_path(maze, s, pt):
            errors.append(f'S无法到达{label} {pt}')

    for r, row in enumerate(maze):
        for c, ch in enumerate(row):
            if ch == 'G':
                if not bfs_path(maze, s, (r, c)):
                    errors.append(f'S无法到达金币({r},{c})')
    return errors


def make_border(rows, cols):
    """生成边界全是墙的迷宫框架"""
    maze = [[' ' for _ in range(cols)] for _ in range(rows)]
    for r in range(rows):
        maze[r][0] = '#'
        maze[r][cols - 1] = '#'
    for c in range(cols):
        maze[0][c] = '#'
        maze[rows - 1][c] = '#'
    return maze


def place_hwall(maze, r, c1, c2):
    """放置水平墙"""
    for c in range(min(c1, c2), max(c1, c2) + 1):
        maze[r][c] = '#'


def place_vwall(maze, c, r1, r2):
    """放置垂直墙"""
    for r in range(min(r1, r2), max(r1, r2) + 1):
        maze[r][c] = '#'


def print_maze(maze):
    """打印迷宫预览"""
    for r, row in enumerate(maze):
        line = ''
        for c, ch in enumerate(row):
            line += '·' if ch == ' ' else ch
        print(f'  {r:2d} {line}')


# ============================================================
# Maze A: 多回路陷阱选择
# 三条回路: 上方(2G+1T=+70), 中间(1G+0T=+50), 下方(3G+3T=+60)
# 算法应优先走中间无陷阱回路
# ============================================================
maze_a = make_border(15, 15)

# 横向隔断
place_hwall(maze_a, 2, 2, 12)
place_hwall(maze_a, 7, 5, 9)
place_hwall(maze_a, 11, 2, 12)
# 纵向隔断
place_vwall(maze_a, 4, 3, 10)
place_vwall(maze_a, 10, 3, 10)

# 开门形成三条回路
maze_a[2][3] = ' '    # 上回路上口
maze_a[2][8] = ' '    # 上回路下口
maze_a[7][7] = ' '    # 中回路通道
maze_a[11][3] = ' '   # 下回路上口
maze_a[11][8] = ' '   # 下回路下口
maze_a[4][7] = ' '    # 左竖墙门
maze_a[8][7] = ' '    # 右竖墙门
maze_a[3][4] = ' '    # 左竖墙通路

# 关键点
maze_a[1][1] = 'S'
maze_a[13][13] = 'E'
maze_a[7][2] = 'B'    # Boss在左侧中间

# 上方回路: 2G + 1T
maze_a[1][5] = 'G'
maze_a[1][7] = 'T'
maze_a[1][11] = 'G'
# 中间回路: 1G (无陷阱)
maze_a[5][8] = 'G'
# 下方回路: 3G + 2T
maze_a[12][5] = 'G'
maze_a[12][6] = 'T'
maze_a[12][9] = 'T'
maze_a[12][11] = 'G'
maze_a[13][8] = 'G'

# ============================================================
# Maze B: 必经陷阱走廊
# 必须经过陷阱才能到达金币区和Boss
# ============================================================
maze_b = make_border(15, 15)

# 外框
place_hwall(maze_b, 3, 2, 12)
place_hwall(maze_b, 11, 2, 12)
place_vwall(maze_b, 3, 3, 11)
place_vwall(maze_b, 11, 3, 11)
# 内框
place_hwall(maze_b, 6, 5, 9)
place_hwall(maze_b, 9, 5, 9)
place_vwall(maze_b, 5, 6, 9)
place_vwall(maze_b, 9, 6, 9)

# 开门形成走廊
maze_b[3][5] = ' '; maze_b[3][8] = ' '
maze_b[6][7] = ' '; maze_b[9][7] = ' '
maze_b[6][5] = ' '; maze_b[9][9] = ' '
maze_b[8][3] = ' '; maze_b[8][11] = ' '
maze_b[11][7] = ' '

# 关键点
maze_b[1][1] = 'S'
maze_b[13][13] = 'E'
maze_b[7][7] = 'B'

# 陷阱：必经之路
maze_b[1][7] = 'T'    # 上方走廊必经
maze_b[8][4] = 'T'    # 内圈入口必经
maze_b[8][10] = 'T'   # Boss右侧必经

# 金币：陷阱后有奖励
maze_b[1][12] = 'G'   # 第1个陷阱后可到达
maze_b[13][4] = 'G'   # 第2个陷阱后可到达
maze_b[7][10] = 'G'   # 第3个陷阱后可到达
maze_b[4][2] = 'G'    # 安全区域

# ============================================================
# Maze C: 分散金币收集
# 金币分散在4个区域，陷阱很少，测试遍历效率
# ============================================================
maze_c = make_border(15, 15)

# 十字分割
place_hwall(maze_c, 7, 2, 12)
place_vwall(maze_c, 7, 2, 12)

# 4个门 + 打通到中心的走廊(竖墙col7从row4到row7)
maze_c[7][4] = ' '; maze_c[7][10] = ' '
maze_c[4][7] = ' '; maze_c[5][7] = ' '; maze_c[6][7] = ' '
maze_c[10][7] = ' '

# 关键点: Boss在十字交叉处(门已打通)
maze_c[1][1] = 'S'
maze_c[13][13] = 'E'
maze_c[7][7] = 'B'

# 左上区金币
maze_c[2][3] = 'G'; maze_c[4][4] = 'G'
# 右上区金币
maze_c[2][10] = 'G'; maze_c[4][10] = 'G'
# 左下区金币
maze_c[9][3] = 'G'; maze_c[11][4] = 'G'
# 右下区金币
maze_c[9][10] = 'G'; maze_c[11][10] = 'G'

# 少量陷阱(可绕行)
maze_c[3][5] = 'T'
maze_c[10][9] = 'T'

# ============================================================
# Maze D: 陷阱密集可绕行
# 8+个陷阱但每个都有安全绕行路线
# ============================================================
maze_d = make_border(15, 15)

# 网格结构
place_vwall(maze_d, 4, 2, 12)
place_vwall(maze_d, 10, 2, 12)
place_hwall(maze_d, 4, 2, 12)
place_hwall(maze_d, 10, 2, 12)

# 开门: 每条墙至少2个门
for r, c in [(2,4),(2,10),(3,4),(3,10),(4,2),(4,3),(4,12),
             (5,4),(5,10),(8,4),(8,10),
             (10,2),(10,3),(10,5),(10,6),(10,11),(10,12),
             (11,4),(11,10),(12,4),(12,10)]:
    if 0 <= r < 15 and 0 <= c < 15:
        maze_d[r][c] = ' '

# 打通中心
maze_d[4][7] = ' '; maze_d[7][4] = ' '
maze_d[7][10] = ' '; maze_d[10][7] = ' '

# 关键点
maze_d[1][1] = 'S'
maze_d[13][13] = 'E'
maze_d[7][7] = 'B'

# 陷阱：放在路口，但每个都有绕行路线
trap_positions = [(2,2),(2,7),(2,12),(7,2),(7,12),(12,2),(12,7),(12,12),(3,5),(9,9)]
for r, c in trap_positions:
    maze_d[r][c] = 'T'

# 金币：在安全位置
gold_positions = [(1,8),(3,3),(6,6),(8,2),(8,8),(8,12),(11,5),(11,8),(13,4)]
for r, c in gold_positions:
    maze_d[r][c] = 'G'

# ============================================================
# Maze E: 多回路绕行测试
# 3层嵌套回路，陷阱挡直路，每个都可以绕行
# ============================================================
maze_e = make_border(15, 15)

# 外圈
place_hwall(maze_e, 3, 3, 11)
place_hwall(maze_e, 11, 3, 11)
place_vwall(maze_e, 3, 3, 11)
place_vwall(maze_e, 11, 3, 11)
# 中圈
place_hwall(maze_e, 5, 5, 9)
place_hwall(maze_e, 9, 5, 9)
place_vwall(maze_e, 5, 5, 9)
place_vwall(maze_e, 9, 5, 9)

# 开门
maze_e[3][5] = ' '; maze_e[3][8] = ' '
maze_e[11][5] = ' '; maze_e[11][8] = ' '
maze_e[5][3] = ' '; maze_e[8][3] = ' '
maze_e[5][11] = ' '; maze_e[8][11] = ' '
maze_e[5][6] = ' '; maze_e[5][8] = ' '
maze_e[9][6] = ' '; maze_e[9][8] = ' '
maze_e[6][5] = ' '; maze_e[8][5] = ' '
maze_e[6][9] = ' '; maze_e[8][9] = ' '

# 关键点
maze_e[1][1] = 'S'
maze_e[13][13] = 'E'
maze_e[7][7] = 'B'

# 金币在回路各处
maze_e[2][7] = 'G'    # 外圈上方
maze_e[4][4] = 'G'    # 外圈左上
maze_e[6][1] = 'G'    # 外圈左侧
maze_e[13][7] = 'G'   # 外圈下方
maze_e[4][8] = 'G'    # 中圈上方
maze_e[8][1] = 'G'    # 中圈左侧

# 陷阱挡直路但可绕行
maze_e[1][7] = 'T'    # 上方直路被挡→走外圈绕
maze_e[7][13] = 'T'   # 右侧直路被挡→走外圈绕
maze_e[4][6] = 'T'    # 中圈上入口附近

# ============================================================
# 验证并保存
# ============================================================
mazes = [
    ('maze_15x15_multi_loop', 'A-多回路陷阱选择', maze_a,
     [15, 12, 10], [[8, 4], [3, 2], [4, 2], [5, 3]], 20, 4),
    ('maze_15x15_mandatory_trap', 'B-必经陷阱走廊', maze_b,
     [18, 14], [[7, 4], [5, 2], [3, 1]], 18, 5),
    ('maze_15x15_scattered', 'C-分散金币收集', maze_c,
     [20, 16], [[9, 5], [4, 2], [6, 3], [3, 1]], 22, 4),
    ('maze_15x15_trap_dense', 'D-陷阱密集可绕行', maze_d,
     [25, 18], [[10, 5], [6, 3], [4, 2], [5, 2]], 25, 3),
    ('maze_15x15_loop_maze', 'E-多回路绕行测试', maze_e,
     [16, 14, 12], [[8, 4], [5, 3], [4, 2]], 20, 5),
]

for fname, label, maze_data, B, skills, minR, coin in mazes:
    errors = validate_maze(maze_data)
    if errors:
        print(f'[{label}] 验证失败:')
        for e in errors:
            print(f'  - {e}')
        continue

    golds = count_ch(maze_data, 'G')
    traps = count_ch(maze_data, 'T')

    data = {
        'maze': maze_data,
        'B': B,
        'PlayerSkills': skills,
        'minRouds': minR,
        'CoinConsumption': coin
    }

    fpath = os.path.join(DATA_DIR, fname + '.json')
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

    print(f'[{label}] OK 已保存: {fname}.json')
    print(f'  金币:{golds}  陷阱:{traps}  BossHP:{B}  技能:{skills}')
    print_maze(maze_data)
    print()

print('=== 5个迷宫全部生成完毕 ===')
