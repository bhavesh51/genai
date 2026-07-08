"""
Project 8 – Educational Content Generator
Bayesian Knowledge Tracing
"""


class BayesianKnowledgeTracer:
    def __init__(self, p_init=0.3, p_learn=0.2, p_forget=0.05, p_guess=0.25, p_slip=0.1):
        self.p_init = p_init
        self.p_learn = p_learn
        self.p_forget = p_forget
        self.p_guess = p_guess
        self.p_slip = p_slip

    def update(self, p_mastery: float, correct: bool) -> float:
        if correct:
            numerator = p_mastery * (1 - self.p_slip)
            denominator = numerator + ((1 - p_mastery) * self.p_guess)
        else:
            numerator = p_mastery * self.p_slip
            denominator = numerator + ((1 - p_mastery) * (1 - self.p_guess))

        posterior = numerator / denominator if denominator else p_mastery
        transitioned = posterior * (1 - self.p_forget) + ((1 - posterior) * self.p_learn)
        return max(0.0, min(1.0, transitioned))

    def get_difficulty(self, p_mastery: float) -> str:
        if p_mastery < 0.3:
            return "beginner"
        if p_mastery < 0.7:
            return "intermediate"
        return "advanced"
