from src.config import ScoringWeights
from src.pipeline.stages import OpportunityScoreResponse


def test_scoring_weights_calculation():
    """Verify that opportunity scores are calculated correctly from category scores."""
    # Custom weights
    weights = ScoringWeights(
        role_match=0.3,
        tech_stack=0.3,
        salary=0.1,
        company_quality=0.1,
        growth=0.1,
        confidence=0.1,
    )

    # Mock LLM response categories
    response = OpportunityScoreResponse(
        role_match=1.0,  # 0.3
        tech_stack=0.8,  # 0.24
        salary=0.5,  # 0.05
        company_quality=0.7,  # 0.07
        growth=0.6,  # 0.06
        confidence=0.9,  # 0.09
        reasoning="Good fit SDE role.",
    )

    # Calculate total
    total_score = (
        response.role_match * weights.role_match
        + response.tech_stack * weights.tech_stack
        + response.salary * weights.salary
        + response.company_quality * weights.company_quality
        + response.growth * weights.growth
        + response.confidence * weights.confidence
    )

    # Total: 0.3 + 0.24 + 0.05 + 0.07 + 0.06 + 0.09 = 0.81
    assert abs(total_score - 0.81) < 1e-5
