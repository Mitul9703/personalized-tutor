"""The course-specific answers supplied by a learner during onboarding."""

from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints


class LearnerProfile(BaseModel):
    level: Literal["beginner", "intermediate", "advanced"]
    goal: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    background: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class OnboardingResponse(BaseModel):
    course_id: str
    profile: LearnerProfile | None
