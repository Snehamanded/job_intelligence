import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models import CandidateProfile
from app.repositories.profiles import ProfileRepository
from app.repositories.resumes import ResumeRepository
from app.schemas.profile import (
    Preferences,
    ProfileData,
    ProfileRead,
    ProfileVersionSummary,
    SourceSpan,
)
from app.services.resume.evidence import profile_experience_months, skill_supported
from app.utils.dates import parse_date_range
from app.utils.locations import normalize_locations
from app.utils.text import TextIndex, contains_folded


class ProfileEditRejectedError(Exception):
    """An edit claims resume support it doesn't have. Message is safe to show."""


def preferences_of(profile: CandidateProfile | None) -> Preferences:
    if profile is None:
        return Preferences()
    return Preferences(
        target_roles=profile.target_roles,
        remote_scope=profile.remote_scope,
        onsite_locations=profile.onsite_locations,
        open_to=profile.open_to,
        min_salary=profile.min_salary,
        currency=profile.currency,
        salary_unknown_policy=profile.salary_unknown_policy,
    )


def to_read(profile: CandidateProfile) -> ProfileRead:
    return ProfileRead(
        id=profile.id,
        version=profile.version,
        origin=profile.origin,
        parse_method=profile.parse_method,
        resume_id=profile.resume_id,
        experience_months=profile.experience_months,
        data=ProfileData.model_validate(profile.data),
        preferences=preferences_of(profile),
        created_at=profile.created_at,
    )


def to_summary(profile: CandidateProfile) -> ProfileVersionSummary:
    return ProfileVersionSummary(
        id=profile.id,
        version=profile.version,
        is_current=profile.is_current,
        origin=profile.origin,
        parse_method=profile.parse_method,
        resume_id=profile.resume_id,
        created_at=profile.created_at,
    )


class ProfileService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._profiles = ProfileRepository(session)
        self._resumes = ResumeRepository(session)

    def current(self, user_id: uuid.UUID) -> CandidateProfile | None:
        return self._profiles.current(user_id)

    def versions(self, user_id: uuid.UUID) -> list[CandidateProfile]:
        return self._profiles.versions(user_id)

    def create_version(
        self,
        user_id: uuid.UUID,
        *,
        data: ProfileData,
        preferences: Preferences,
        origin: str,
        parse_method: str | None,
        resume_id: uuid.UUID | None,
        today: date | None = None,
    ) -> CandidateProfile:
        preferences = preferences.model_copy(
            update={"onsite_locations": normalize_locations(preferences.onsite_locations)}
        )
        profile = CandidateProfile(
            user_id=user_id,
            resume_id=resume_id,
            origin=origin,
            parse_method=parse_method,
            data=data.model_dump(mode="json"),
            experience_months=profile_experience_months(data, today),
            **preferences.model_dump(),
        )
        return self._profiles.add_version(profile)

    def update(
        self, user_id: uuid.UUID, data: ProfileData, preferences: Preferences
    ) -> CandidateProfile:
        current = self._profiles.current(user_id)
        resume_id = current.resume_id if current else None
        resume = self._resumes.get(user_id, resume_id) if resume_id else None
        verified = self._reverify(data, resume.extracted_text if resume else None)
        profile = self.create_version(
            user_id,
            data=verified,
            preferences=preferences,
            origin="edited",
            parse_method=current.parse_method if current else None,
            resume_id=resume_id,
        )
        self._session.commit()
        return profile

    @staticmethod
    def _reverify(data: ProfileData, resume_text: str | None) -> ProfileData:
        """Re-check every item the client says came from the resume; recompute spans server-side.

        Items marked `source: user` are the user's own statements: kept, labeled, without spans.
        """
        index = TextIndex(resume_text) if resume_text else None

        def span_for(label: str, evidence: str | None, mentions: str | None) -> SourceSpan:
            found = index.find(evidence) if index and evidence else None
            if found is None:
                raise ProfileEditRejectedError(
                    f'"{label}" is marked as coming from your resume, but its quote is not in the '
                    "resume. Mark it as added by you instead."
                )
            if mentions is not None and not contains_folded(evidence or "", mentions):
                raise ProfileEditRejectedError(
                    f'"{label}" does not match the resume text it quotes. Mark it as added by you.'
                )
            return SourceSpan(start=found[0], end=found[1])

        for skill in data.skills:
            if skill.source == "resume":
                skill.source_span = span_for(skill.name, skill.evidence, None)
                if not skill_supported(skill.name, skill.evidence or ""):
                    raise ProfileEditRejectedError(
                        f'"{skill.name}" is not mentioned in the resume text it quotes.'
                    )
            else:
                skill.evidence, skill.source_span = None, None
        for exp in data.experience:
            if exp.source == "resume":
                exp.source_span = span_for(exp.title, exp.evidence, exp.title)
                span_for(exp.company, exp.evidence, exp.company)
                for bullet in exp.bullets:
                    if bullet.source == "resume":
                        bullet.source_span = span_for(bullet.text, bullet.text, None)
                        bullet.evidence = bullet.text
                    else:
                        bullet.evidence, bullet.source_span = None, None
            else:
                exp.evidence, exp.source_span = None, None
                for bullet in exp.bullets:
                    bullet.source, bullet.evidence, bullet.source_span = "user", None, None
            dates = parse_date_range(exp.date_text)
            exp.start = str(dates.start) if dates else None
            exp.end = str(dates.end) if dates and dates.end else None
            exp.is_current = bool(dates and dates.is_current)
        for project in data.projects:
            if project.source == "resume":
                project.source_span = span_for(project.name, project.evidence, project.name)
            else:
                project.evidence, project.source_span = None, None
        for edu in data.education:
            if edu.source == "resume":
                edu.source_span = span_for(edu.institution, edu.evidence, edu.institution)
            else:
                edu.evidence, edu.source_span = None, None
        for cert in data.certifications:
            if cert.source == "resume":
                cert.source_span = span_for(cert.name, cert.evidence, cert.name)
            else:
                cert.evidence, cert.source_span = None, None
        return data
