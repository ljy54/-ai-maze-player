"""
AI玩家引擎：统一入口，包含两个独立任务
- 任务一 (greedy)：贪心实时资源拾取 — 评价指标：平均拾取资源价值
- 任务二 (global)：全局最优探索 — 评价指标：抵终点时剩余资源价值
"""
from typing import List, Tuple
from .maze_parser import MazeParser
from .pathfinder import PathFinder
from .boss_simulator import BossSimulator
from .greedy_player import GreedyPlayer


class AIEngine:
    """AI决策引擎：整合路径规划与Boss战斗优化"""

    # ============================================================
    #  任务一：贪心实时资源拾取
    #  评价指标：平均拾取资源价值（多迷宫取均值）
    #  算法：有限视野 + 贪心性价比选择
    # ============================================================
    def solve_greedy(self, maze: List[List[str]], boss_hps: List[int],
                     player_skills: List[List[int]], min_rounds: int,
                     coin_consumption: int, vision_range: int = 1) -> dict:
        """任务一：贪心AI求解"""
        skills = [(s[0], s[1]) for s in player_skills]

        # Step 1: 运行贪心玩家 S→Boss
        player = GreedyPlayer(maze, vision_range=vision_range)
        greedy_result = player.run(debug=True)

        # Step 2: 检查是否到达Boss
        reached_boss = greedy_result["reachedBoss"]

        # Step 3: Boss战斗
        can_beat = False
        rounds_needed = 0
        skill_seq = []
        boss_defeated = False
        revival_cost = 0

        if reached_boss:
            simulator = BossSimulator(boss_hps, skills, min_rounds)
            can_beat, rounds_needed, skill_seq = simulator.solve()

            # 找E位置
            end_pos = (-1, -1)
            for r in range(len(maze)):
                for c in range(len(maze[0])):
                    if maze[r][c] == 'E': end_pos = (r, c)

            if can_beat:
                boss_defeated = True
                # Boss→E：复用同一套 _best_direction 评分逻辑
                player._walk_to(end_pos)
            else:
                extra = max(0, rounds_needed - min_rounds)
                revival_cost = extra * coin_consumption
                # 用 player 当前状态判断是否能支付复活费用
                current_net = player.collected_gold - player.traps_hit * 30
                if current_net >= revival_cost:
                    boss_defeated = True
                    player._walk_to(end_pos)

        # 最终路径和评分：player内部已追加B→E部分，用最终状态重新计算 stats
        path = player.path
        all_step_scores = player._step_scores

        # 从 player 最终状态重新计算（包含 B→E 段的收集）
        TRAP_COST = 30
        total_gold = player.collected_gold
        traps_hit = player.traps_hit
        trap_damage = traps_hit * TRAP_COST
        net_from_path = total_gold - trap_damage
        final_net = net_from_path - revival_cost
        reached_end = boss_defeated and len(path) > 0 and maze[path[-1][0]][path[-1][1]] == 'E'

        return {
            "path": path,
            "skillSequence": [
                {"round": s[0] + 1, "skillIndex": s[1], "targetBoss": s[2]}
                for s in skill_seq
            ],
            "stats": {
                "totalCoins": total_gold,
                "collectedGolds": total_gold // 50,
                "trapDamage": trap_damage,
                "trapsHit": traps_hit,
                "bossDefeated": boss_defeated,
                "roundsUsed": rounds_needed,
                "minRounds": min_rounds,
                "revivalCost": revival_cost,
                "netCoins": final_net,
                "pathLength": len(path),
                "reachedEnd": reached_end,
            },
            # 任务一特有评价字段
            "evaluation": {
                "strategy": "greedy",
                "visionRange": vision_range,
                "primaryMetric": "averageCollectedResourceValue",
                "description": "评价指标：平均拾取资源价值。需要在多个不同迷宫上运行取均值",
                "collectedValue": total_gold,
                "trapPenalty": trap_damage,
                "netValue": net_from_path,
            },
            "stepScores": all_step_scores,
        }

    # ============================================================
    #  任务二：全局最优探索
    #  评价指标：抵终点时剩余资源价值 + 步数/基准值
    #  算法：全迷宫已知 + DP路径规划 + 分支定界Boss战
    # ============================================================
    def solve_global(self, maze: List[List[str]], boss_hps: List[int],
                     player_skills: List[List[int]], min_rounds: int,
                     coin_consumption: int) -> dict:
        """任务二：全局最优AI求解"""
        skills = [(s[0], s[1]) for s in player_skills]

        # Step 1: 解析迷宫
        parser = MazeParser(maze)

        # Step 2: DP路径规划
        pathfinder = PathFinder(parser)
        best_path, net_gold, collected = pathfinder.find_best_path()

        # Step 3: 统计路径实际经过的金币和陷阱
        path_gold_positions = set()
        path_trap_positions = set()
        for pt in best_path:
            ch = parser.maze[pt[0]][pt[1]]
            if ch == "G":
                path_gold_positions.add(pt)
            elif ch == "T":
                path_trap_positions.add(pt)

        actual_gold = len(path_gold_positions) * 50
        trap_loss = len(path_trap_positions) * 30
        net_from_path = actual_gold - trap_loss

        # Step 4: Boss战斗
        simulator = BossSimulator(boss_hps, skills, min_rounds)
        can_beat, rounds_needed, skill_seq = simulator.solve()

        # Step 5: 综合评估
        revival_cost = 0
        boss_defeated = can_beat
        if not can_beat:
            extra = max(0, rounds_needed - min_rounds)
            revival_cost = extra * coin_consumption
            if net_from_path >= revival_cost:
                boss_defeated = True

        final_net = net_from_path - revival_cost

        return {
            "path": best_path,
            "skillSequence": [
                {"round": s[0] + 1, "skillIndex": s[1], "targetBoss": s[2]}
                for s in skill_seq
            ],
            "stats": {
                "totalCoins": actual_gold,
                "collectedGolds": len(path_gold_positions),
                "trapDamage": trap_loss,
                "bossDefeated": boss_defeated,
                "roundsUsed": rounds_needed,
                "minRounds": min_rounds,
                "revivalCost": revival_cost,
                "netCoins": final_net,
                "pathLength": len(best_path),
            },
            # 任务二特有评价字段
            "evaluation": {
                "strategy": "global_optimal",
                "algorithms": ["DP_path_planning", "branch_and_bound_boss"],
                "primaryMetric": "remainingResourceValueAtEnd",
                "secondaryMetric": "stepsToBenchmarkRatio",
                "description": "评价指标：抵达终点时剩余资源价值。值越大越好",
                "remainingValue": final_net,
                "totalCollected": actual_gold,
                "pathSteps": len(best_path),
            },
        }
