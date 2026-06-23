from typing import List, Tuple, Set, Dict
from collections import deque


class MazeParser:
    """迷宫解析：提取关键点，计算可达性和距离"""

    def __init__(self, maze: List[List[str]]):
        self.maze = maze
        self.rows = len(maze)
        self.cols = len(maze[0]) if self.rows > 0 else 0
        self.start: Tuple[int, int] = (-1, -1)
        self.end: Tuple[int, int] = (-1, -1)
        self.boss_pos: Tuple[int, int] = (-1, -1)
        self.golds: List[Tuple[int, int]] = []
        self.traps: List[Tuple[int, int]] = []
        self._parse()

    def _parse(self):
        for r in range(self.rows):
            for c in range(self.cols):
                ch = self.maze[r][c]
                if ch == "S":
                    self.start = (r, c)
                elif ch == "E":
                    self.end = (r, c)
                elif ch == "B":
                    self.boss_pos = (r, c)
                elif ch == "G":
                    self.golds.append((r, c))
                elif ch == "T":
                    self.traps.append((r, c))

    def is_passable(self, r: int, c: int) -> bool:
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return self.maze[r][c] != "#"
        return False

    def get_neighbors(self, pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        r, c = pos
        neighbors = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if self.is_passable(nr, nc):
                neighbors.append((nr, nc))
        return neighbors

    def bfs_distance(self, start: Tuple[int, int]) -> Dict[Tuple[int, int], int]:
        """BFS计算从start到所有可通行点的最短距离"""
        dist = {start: 0}
        q = deque([start])
        while q:
            cur = q.popleft()
            for nb in self.get_neighbors(cur):
                if nb not in dist:
                    dist[nb] = dist[cur] + 1
                    q.append(nb)
        return dist

    def get_all_key_points(self) -> List[Tuple[int, int]]:
        """返回所有关键点：S, E, B, 所有G, 所有T"""
        points = [self.start, self.end, self.boss_pos]
        points.extend(self.golds)
        points.extend(self.traps)
        return [p for p in points if p != (-1, -1)]
