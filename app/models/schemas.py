from pydantic import BaseModel
from typing import List, Tuple


class SkillUsage(BaseModel):
    round: int
    skillIndex: int
    targetBoss: int


class SolveResponse(BaseModel):
    success: bool
    path: List[Tuple[int, int]] = []
    skillSequence: List[SkillUsage] = []
    stats: dict = {}
    message: str = ""
    stepScores: list = []  # 任务一每步方向评分
