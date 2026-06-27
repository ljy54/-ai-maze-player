"""
AI玩家任务二：九宫格视野 + 贪心最优路径规划
- 视野严格限制为 3×3 九宫格
- 在可见区域内贪心选择性价比最高的金币去收集
- 已走过的位置会被记忆，避免重复踩陷阱
- 评价指标：资源获取与路径步数的比值最大化
- 停止条件：九宫格内无未收集资源，不强制找出口
"""
from typing import List, Tuple, Set, Optional
from collections import deque

# 资源价值常量
GOLD_VALUE = 50
TRAP_COST = 30


class LocalOptimalPlayer:
    """局部贪心最优AI玩家：3×3视野 + 记忆 + 贪心选择可见最佳金币"""

    def __init__(self, maze: List[List[str]], vision_range: int = 1):
        self.maze = [list(row) for row in maze]
        self.rows = len(maze)
        self.cols = len(maze[0]) if self.rows > 0 else 0
        self.vision = vision_range

        # 起点：同时支持 'S' 和 'P'（case-maze格式用P）
        self.start = self._find_start()

        # 当前状态
        self.pos = self.start
        self.collected_gold = 0
        self.traps_hit = 0
        self.path: List[Tuple[int, int]] = [self.start]
        self.visited: Set[Tuple[int, int]] = {self.start}
        self.collected_positions: Set[Tuple[int, int]] = set()

        # 记忆：已发现但未收集的资源位置
        self.known_golds: Set[Tuple[int, int]] = set()
        self.known_traps: Set[Tuple[int, int]] = set()

        # 每步评分数据（前端可视化用）
        self._step_scores: list = []

    # ============================================================
    #  基础工具方法
    # ============================================================

    def _find_start(self) -> Tuple[int, int]:
        """寻找起点：支持 'S' 或 'P'"""
        for r in range(self.rows):
            for c in range(self.cols):
                if self.maze[r][c] in ('S', 'P'):
                    return (r, c)
        return (-1, -1)

    def _find(self, ch: str) -> Tuple[int, int]:
        for r in range(self.rows):
            for c in range(self.cols):
                if self.maze[r][c] == ch:
                    return (r, c)
        return (-1, -1)

    def is_passable(self, r: int, c: int) -> bool:
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            return False
        return self.maze[r][c] != '#'

    def get_neighbors(self, pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        """获取四个方向的可通行邻居"""
        r, c = pos
        nb = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if self.is_passable(nr, nc):
                nb.append((nr, nc))
        return nb

    # ============================================================
    #  视野扫描
    # ============================================================

    def scan_visible(self) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
        """扫描3×3视野内的未收集金币和陷阱，更新记忆。
        返回 (可见金币列表, 可见陷阱列表)"""
        r0, c0 = self.pos
        golds = []
        traps = []
        for r in range(max(0, r0 - self.vision),
                       min(self.rows, r0 + self.vision + 1)):
            for c in range(max(0, c0 - self.vision),
                           min(self.cols, c0 + self.vision + 1)):
                pt = (r, c)
                if pt in self.collected_positions:
                    continue
                ch = self.maze[r][c]
                if ch == 'G':
                    golds.append(pt)
                    self.known_golds.add(pt)
                elif ch == 'T':
                    traps.append(pt)
                    self.known_traps.add(pt)
        return golds, traps

    # ============================================================
    #  路径搜索
    # ============================================================

    def _bfs_path(self, start: Tuple[int, int],
                  end: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        """BFS 寻找从 start 到 end 的最短路径（全图范围）。
        返回路径（包含起点和终点），不可达返回 None。"""
        if start == end:
            return [start]

        prev = {start: None}
        q = deque([start])
        while q:
            cur = q.popleft()
            if cur == end:
                break
            for nb in self.get_neighbors(cur):
                if nb not in prev:
                    prev[nb] = cur
                    q.append(nb)

        if end not in prev:
            return None

        # 回溯路径
        path = []
        cur = end
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return path

    def _count_traps_on_path(self, path: List[Tuple[int, int]],
                             exclude_start: bool = True) -> int:
        """统计路径上经过的陷阱数量。
        exclude_start=True 时排除起点。
        已收集过的陷阱不计入（走过一次不再扣分）。"""
        count = 0
        start_idx = 1 if exclude_start else 0
        for pt in path[start_idx:]:
            if pt in self.known_traps and pt not in self.collected_positions:
                count += 1
        return count

    # ============================================================
    #  贪心评估：在可见金币中选择性价比最高的
    # ============================================================

    def _evaluate_visible_golds(self, visible_golds: List[Tuple[int, int]]
                                ) -> Tuple[Optional[Tuple[int, int]], float,
                                           Optional[List[Tuple[int, int]]], list]:
        """
        对每个可见金币，计算 "资源价值/路径成本" 比值。
        返回 (最佳金币, 比值, 到该金币的路径, 所有候选详情列表)。
        """
        candidates = []

        if not visible_golds:
            return None, 0, None, candidates

        best_ratio = -999999.0
        best_gold = None
        best_path = None

        for gold in visible_golds:
            path = self._bfs_path(self.pos, gold)
            if path is None or len(path) < 2:
                continue

            dist = len(path) - 1
            traps_on_path = self._count_traps_on_path(path)
            net_gain = GOLD_VALUE - traps_on_path * TRAP_COST
            ratio = net_gain / max(dist, 1)

            candidates.append({
                "pos": list(gold),
                "dist": dist,
                "traps": traps_on_path,
                "netGain": net_gain,
                "ratio": round(ratio, 2),
                "source": "visible",
            })

            if ratio > best_ratio:
                best_ratio = ratio
                best_gold = gold
                best_path = path

        # 标记选中的
        for c in candidates:
            c["chosen"] = (tuple(c["pos"]) == best_gold)

        return (best_gold, best_ratio, best_path, candidates) if best_gold else (None, 0, None, candidates)

    # ============================================================
    #  记忆中的金币评估（当视野内无金币时用记忆补充）
    # ============================================================

    def _evaluate_known_golds(self
                              ) -> Tuple[Optional[Tuple[int, int]], float,
                                         Optional[List[Tuple[int, int]]], list]:
        """
        评估记忆中已知但不可见（超出3×3范围）的金币。
        返回 (最佳金币, 比值, 路径, 所有候选详情列表)。
        """
        candidates = []
        available = [g for g in self.known_golds
                     if g not in self.collected_positions]
        if not available:
            return None, 0, None, candidates

        best_ratio = -999999.0
        best_gold = None
        best_path = None

        for gold in available:
            path = self._bfs_path(self.pos, gold)
            if path is None or len(path) < 2:
                continue

            dist = len(path) - 1
            traps_on_path = self._count_traps_on_path(path)
            net_gain = GOLD_VALUE - traps_on_path * TRAP_COST
            ratio = net_gain / max(dist, 1)

            candidates.append({
                "pos": list(gold),
                "dist": dist,
                "traps": traps_on_path,
                "netGain": net_gain,
                "ratio": round(ratio, 2),
                "source": "memory",
            })

            if ratio > best_ratio:
                best_ratio = ratio
                best_gold = gold
                best_path = path

        for c in candidates:
            c["chosen"] = (tuple(c["pos"]) == best_gold)

        return (best_gold, best_ratio, best_path, candidates) if best_gold else (None, 0, None, candidates)

    # ============================================================
    #  四方向评分（与任务一格式一致，前端共用渲染）
    # ============================================================

    def _score_directions(self, next_step: Tuple[int, int]) -> dict:
        """
        对4个方向评分，格式与任务一完全一致。
        next_step: BFS路径下一步（标记为选中方向）。
        """
        r0, c0 = self.pos
        scores = {}

        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r0 + dr, c0 + dc
            dir_key = f"({dr:+d},{dc:+d})"

            if not self.is_passable(nr, nc):
                scores[dir_key] = {
                    "pos": [nr, nc],
                    "ch": "#",
                    "score": -999,
                    "details": ["墙"],
                    "chosen": False,
                }
                continue

            score = 0.0
            parts = []
            cell_ch = self.maze[nr][nc]

            # 步数成本
            score -= 1.5

            # 直接踩到的资源（未收集的）
            if (nr, nc) not in self.collected_positions:
                if cell_ch == 'G':
                    score += GOLD_VALUE
                    parts.append(f"金币+{GOLD_VALUE}")
                elif cell_ch == 'T':
                    score -= TRAP_COST
                    parts.append(f"陷阱-{TRAP_COST}")

            # 该方向可见区域内的资源引力
            for r in range(max(0, r0 - 1), min(self.rows, r0 + 2)):
                for c in range(max(0, c0 - 1), min(self.cols, c0 + 2)):
                    if (r, c) == self.pos or (r, c) in self.collected_positions:
                        continue
                    in_dir = False
                    if dr == -1 and r < r0: in_dir = True
                    elif dr == 1 and r > r0: in_dir = True
                    elif dc == -1 and c < c0: in_dir = True
                    elif dc == 1 and c > c0: in_dir = True
                    if not in_dir:
                        continue
                    dist = abs(r - r0) + abs(c - c0)
                    ch = self.maze[r][c]
                    if ch == 'G':
                        val = GOLD_VALUE / dist
                        score += val
                        parts.append(f"G({r},{c})+{val:.1f}")
                    elif ch == 'T':
                        val = TRAP_COST / dist
                        score -= val
                        parts.append(f"T({r},{c})-{val:.1f}")

            # 记忆中的金币在该方向的引力
            for g in self.known_golds:
                if g in self.collected_positions:
                    continue
                gr, gc = g
                if abs(gr - r0) <= 1 and abs(gc - c0) <= 1:
                    continue  # 视野内已算过
                in_dir = False
                if dr == -1 and gr < r0: in_dir = True
                elif dr == 1 and gr > r0: in_dir = True
                elif dc == -1 and gc < c0: in_dir = True
                elif dc == 1 and gc > c0: in_dir = True
                if in_dir:
                    dist = max(abs(gr - r0) + abs(gc - c0), 1)
                    val = GOLD_VALUE / dist
                    score += val
                    parts.append(f"忆G({gr},{gc})+{val:.1f}")

            # 重复访问惩罚
            if (nr, nc) in self.visited:
                score -= 2.0
                parts.append("已访-2")

            # 是否BFS路径下一步
            is_chosen = (nr, nc) == next_step

            scores[dir_key] = {
                "pos": [nr, nc],
                "ch": cell_ch,
                "score": round(score, 2),
                "details": parts,
                "chosen": is_chosen,
            }

        return scores

    # ============================================================
    #  资源收集
    # ============================================================

    def collect_at(self, pos: Tuple[int, int]):
        """在当前位置收集资源"""
        if pos in self.collected_positions:
            return
        ch = self.maze[pos[0]][pos[1]]
        if ch == 'G':
            self.collected_gold += GOLD_VALUE
            self.collected_positions.add(pos)
            self.known_golds.discard(pos)
        elif ch == 'T':
            self.traps_hit += 1
            self.collected_positions.add(pos)
            self.known_traps.discard(pos)

    # ============================================================
    #  主循环
    # ============================================================

    def run(self, debug: bool = False) -> dict:
        """
        运行任务二AI：3×3视野 + 贪心选最佳资源 + 记忆
        停止条件：可见范围内无未收集金币
        """
        max_steps = self.rows * self.cols * 3
        step = 0
        stop_reason = "无可探索资源"

        while step < max_steps:
            step += 1

            # 1. 扫描3×3视野
            visible_golds, visible_traps = self.scan_visible()

            # 2. 停止条件：视野内和记忆中均无未收集金币
            available_known = [g for g in self.known_golds
                              if g not in self.collected_positions]
            if not visible_golds and not available_known:
                stop_reason = "视野和记忆中均无未收集金币"
                if debug:
                    print(f"  [停止] {stop_reason} (步数={step})")
                break

            # 3. 可见金币优先；视野无金币时用记忆导航
            source_type = "visible"
            if not visible_golds:
                source_type = "memory"
                if debug:
                    print(f"  [记忆] 视野内无金币，用记忆导航")
                target_gold, ratio, path, candidates = self._evaluate_known_golds()
            else:
                target_gold, ratio, path, candidates = self._evaluate_visible_golds(visible_golds)

            if target_gold is None:
                stop_reason = "无可达金币"
                if debug:
                    print(f"  [警告] {stop_reason}，停止")
                break

            # 2.5 比值收益检查：吃下一个金币后累计比值是否下降
            current_move = len(self.path) - 1
            current_net = self.collected_gold - self.traps_hit * TRAP_COST
            current_ratio = current_net / max(current_move, 1)

            dist_to_gold = len(path) - 1
            traps_to_gold = self._count_traps_on_path(path)
            future_net = current_net + GOLD_VALUE - traps_to_gold * TRAP_COST
            future_moves = current_move + dist_to_gold
            future_ratio = future_net / max(future_moves, 1)

            if future_ratio < current_ratio and current_move > 0:
                stop_reason = f"比值收益下降（当前{current_ratio:.2f} -> 吃完后{future_ratio:.2f}）"
                if debug:
                    print(f"  [停止] {stop_reason} (步数={step})")
                break

            next_pos = path[1]  # BFS路径的下一步

            # 构建步评分数据（候选金币 + 四方向评分）
            dir_scores = self._score_directions(next_pos)
            self._step_scores.append({
                "pos": list(self.pos),
                "scores": dir_scores,           # 四方向评分（与任务一格式一致）
                "candidates": candidates,       # 候选金币详情
                "chosenTarget": list(target_gold),
                "source": source_type,
                "targetRatio": round(ratio, 2),
                "stats": {
                    "netGold": current_net,
                    "moveCount": current_move,
                    "ratio": round(current_ratio, 2),
                },
            })

            if debug:
                print(f"  [目标] 金币: {target_gold} 比值={ratio:.2f}"
                      f" 距离={len(path)-1}步 金币+{GOLD_VALUE}")

            if next_pos == self.pos:
                stop_reason = "无法移动"
                if debug:
                    print(f"  [错误] {stop_reason}，停止")
                break

            # 5. 移动
            self.pos = next_pos
            self.path.append(self.pos)
            self.visited.add(self.pos)
            already_collected = self.pos in self.collected_positions
            self.collect_at(self.pos)

            if debug:
                ch = self.maze[self.pos[0]][self.pos[1]]
                if already_collected:
                    print(f"  [移动] 到 ({self.pos[0]},{self.pos[1]}) (已收集)")
                elif ch in ('G', 'T'):
                    print(f"  [收集] ({self.pos[0]},{self.pos[1]}) {ch}")
                else:
                    print(f"  [移动] 到 ({self.pos[0]},{self.pos[1]})")

        # 统计（步数不含起点）
        trap_loss = self.traps_hit * TRAP_COST
        net_gold = self.collected_gold - trap_loss
        move_count = len(self.path) - 1  # 实际移动步数
        ratio = net_gold / max(move_count, 1)

        return {
            "path": self.path,
            "totalGold": self.collected_gold,
            "trapDamage": trap_loss,
            "trapsHit": self.traps_hit,
            "netGold": net_gold,
            "pathLength": move_count,
            "ratio": round(ratio, 3),
            "reachedBoss": False,
            "reachedEnd": False,
            "visionRange": self.vision,
            "strategy": "local_optimal_greedy",
            "stopReason": stop_reason,
            "stepScores": self._step_scores,
        }