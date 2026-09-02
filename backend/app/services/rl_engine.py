# TODO: Q-learning-based adaptive difficulty engine.
# State: recent answer scores + current difficulty tier.
# Action: {easier, same, harder}.
# Reward: weighted combination of content_score + delivery_score.
# See docs/architecture.md ("Adaptive Interview Engine") for the design
# rationale (tabular Q-learning chosen over deep RL for feasibility).


def select_next_difficulty(recent_scores: list[float], current_difficulty: int) -> int:
    raise NotImplementedError
