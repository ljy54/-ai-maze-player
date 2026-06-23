from pydantic import BaseModel
from typing import List, Tuple


class SolveRequest(BaseModel):
    maze: List[List[str]]
    B: List[int]  # Boss血量序列
    PlayerSkills: List[List[int]]  # [[damage, cooldown], ...]
    minRounds: int  # 注意：输入JSON中是 "minRouds"（拼写错误），此处兼容
    CoinConsumption: int

    @classmethod
    def parse(cls, data: dict) -> "SolveRequest":
        maze = data["maze"]
        bosses = data["B"]
        skills = data["PlayerSkills"]
        min_rounds = data.get("minRouds", data.get("minRounds", 20))
        coin_consumption = data.get("CoinConsumption", data.get("coinConsumption", 5))
        return cls(
            maze=maze,
            B=bosses,
            PlayerSkills=skills,
            minRounds=min_rounds,
            CoinConsumption=coin_consumption,
        )


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


class ValidateResponse(BaseModel):
    valid: bool
    message: str = ""
    details: dict = {}
