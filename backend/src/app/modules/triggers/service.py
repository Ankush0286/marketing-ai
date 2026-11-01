import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.common.enums import PlatformType, TriggerMatchStatus
from app.modules.accounts.exceptions import AccountNotFoundError
from app.modules.accounts.models import ConnectedAccount
from app.modules.triggers.commands import (
    AddWatchedHandleCommand,
    CreateTriggerRuleCommand,
    EvaluateIncomingPostCommand,
    ReviewMatchCommand,
    UpdateTriggerRuleCommand,
    UpdateWatchedHandleCommand,
)
from app.modules.triggers.exceptions import (
    InvalidTriggerRuleError,
    TriggerMatchNotFoundError,
    TriggerRuleNotFoundError,
    WatchedHandleAlreadyExistsError,
    WatchedHandleNotFoundError,
)
from app.modules.triggers.models import TriggerMatch, TriggerRule, WatchedHandle


def _ensure_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


class TriggerService:
    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # Watched Handle Management
    # =========================================================================

    def get_watched_handle_by_id(self, handle_id: UUID | str) -> WatchedHandle | None:
        target_id = _ensure_uuid(handle_id)
        return (
            self.db.query(WatchedHandle)
            .filter(WatchedHandle.id == target_id)
            .first()
        )

    def get_watched_handle_by_id_or_raise(self, handle_id: UUID | str) -> WatchedHandle:
        handle = self.get_watched_handle_by_id(handle_id)
        if not handle:
            raise WatchedHandleNotFoundError(handle_id)
        return handle

    def get_watched_handle_by_platform_and_handle(
        self, platform: PlatformType, handle: str
    ) -> WatchedHandle | None:
        clean_handle = handle.lstrip("@").strip()
        return (
            self.db.query(WatchedHandle)
            .filter(
                WatchedHandle.platform == platform,
                WatchedHandle.handle == clean_handle,
            )
            .first()
        )

    def list_watched_handles(self, active_only: bool = False) -> list[WatchedHandle]:
        query = self.db.query(WatchedHandle).order_by(WatchedHandle.created_at.desc())
        if active_only:
            query = query.filter(WatchedHandle.is_active.is_(True))
        return query.all()

    def add_watched_handle(self, cmd: AddWatchedHandleCommand) -> WatchedHandle:
        clean_handle = cmd.handle.lstrip("@").strip()
        existing = self.get_watched_handle_by_platform_and_handle(cmd.platform, clean_handle)
        if existing:
            platform_str = cmd.platform.value if hasattr(cmd.platform, "value") else str(cmd.platform)
            raise WatchedHandleAlreadyExistsError(platform=platform_str, handle=clean_handle)

        watched = WatchedHandle(
            platform=cmd.platform,
            handle=clean_handle,
            display_name=cmd.display_name,
            scrape_frequency_minutes=cmd.scrape_frequency_minutes,
            extra_metadata=cmd.extra_metadata,
        )
        self.db.add(watched)
        self.db.commit()
        self.db.refresh(watched)
        return watched

    def update_watched_handle(self, cmd: UpdateWatchedHandleCommand) -> WatchedHandle:
        watched = self.get_watched_handle_by_id_or_raise(cmd.handle_id)

        if cmd.display_name is not None:
            watched.display_name = cmd.display_name
        if cmd.is_active is not None:
            watched.is_active = cmd.is_active
        if cmd.scrape_frequency_minutes is not None:
            watched.scrape_frequency_minutes = cmd.scrape_frequency_minutes
        if cmd.extra_metadata is not None:
            watched.extra_metadata = cmd.extra_metadata

        self.db.commit()
        self.db.refresh(watched)
        return watched

    def delete_watched_handle(self, handle_id: UUID | str) -> None:
        watched = self.get_watched_handle_by_id_or_raise(handle_id)
        # Delete dependent matches first to avoid foreign key issues
        self.db.query(TriggerMatch).filter(TriggerMatch.watched_handle_id == watched.id).delete(
            synchronize_session="fetch"
        )
        self.db.delete(watched)
        self.db.commit()

    # =========================================================================
    # Trigger Rule Management
    # =========================================================================

    def get_rule_by_id(self, rule_id: UUID | str) -> TriggerRule | None:
        target_id = _ensure_uuid(rule_id)
        return (
            self.db.query(TriggerRule)
            .filter(TriggerRule.id == target_id)
            .first()
        )

    def get_rule_by_id_or_raise(self, rule_id: UUID | str) -> TriggerRule:
        rule = self.get_rule_by_id(rule_id)
        if not rule:
            raise TriggerRuleNotFoundError(rule_id)
        return rule

    def list_rules(
        self, platform: PlatformType | None = None, active_only: bool = False
    ) -> list[TriggerRule]:
        query = self.db.query(TriggerRule).order_by(TriggerRule.created_at.desc())
        if platform is not None:
            query = query.filter(TriggerRule.platform == platform)
        if active_only:
            query = query.filter(TriggerRule.is_active.is_(True))
        return query.all()

    def create_rule(self, cmd: CreateTriggerRuleCommand) -> TriggerRule:
        account = (
            self.db.query(ConnectedAccount)
            .filter(ConnectedAccount.id == cmd.account_id)
            .first()
        )
        if not account:
            raise AccountNotFoundError(cmd.account_id)

        if cmd.watched_handle_id:
            self.get_watched_handle_by_id_or_raise(cmd.watched_handle_id)

        clean_any = [k.lower().strip() for k in cmd.keywords_any if k.strip()]
        clean_all = [k.lower().strip() for k in cmd.keywords_all if k.strip()]
        clean_exclude = [k.lower().strip() for k in cmd.keywords_exclude if k.strip()]

        if not clean_any and not clean_all:
            raise InvalidTriggerRuleError("Rule requires at least one keyword in keywords_any or keywords_all.")

        rule = TriggerRule(
            name=cmd.name,
            description=cmd.description,
            platform=cmd.platform,
            account_id=cmd.account_id,
            watched_handle_id=cmd.watched_handle_id,
            action_type=cmd.action_type,
            keywords_any=clean_any,
            keywords_all=clean_all,
            keywords_exclude=clean_exclude,
            response_template=cmd.response_template,
            cooldown_minutes=cmd.cooldown_minutes,
            is_active=cmd.is_active,
            extra_metadata=cmd.extra_metadata,
        )
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def update_rule(self, cmd: UpdateTriggerRuleCommand) -> TriggerRule:
        rule = self.get_rule_by_id_or_raise(cmd.rule_id)

        if cmd.account_id is not None:
            account = (
                self.db.query(ConnectedAccount)
                .filter(ConnectedAccount.id == cmd.account_id)
                .first()
            )
            if not account:
                raise AccountNotFoundError(cmd.account_id)
            rule.account_id = cmd.account_id

        if cmd.watched_handle_id is not None:
            self.get_watched_handle_by_id_or_raise(cmd.watched_handle_id)
            rule.watched_handle_id = cmd.watched_handle_id

        if cmd.name is not None:
            rule.name = cmd.name
        if cmd.description is not None:
            rule.description = cmd.description
        if cmd.action_type is not None:
            rule.action_type = cmd.action_type
        if cmd.keywords_any is not None:
            rule.keywords_any = [k.lower().strip() for k in cmd.keywords_any if k.strip()]
        if cmd.keywords_all is not None:
            rule.keywords_all = [k.lower().strip() for k in cmd.keywords_all if k.strip()]
        if cmd.keywords_exclude is not None:
            rule.keywords_exclude = [k.lower().strip() for k in cmd.keywords_exclude if k.strip()]
        if cmd.response_template is not None:
            rule.response_template = cmd.response_template
        if cmd.cooldown_minutes is not None:
            rule.cooldown_minutes = cmd.cooldown_minutes
        if cmd.is_active is not None:
            rule.is_active = cmd.is_active
        if cmd.extra_metadata is not None:
            rule.extra_metadata = cmd.extra_metadata

        self.db.commit()
        self.db.refresh(rule)
        return rule

    def delete_rule(self, rule_id: UUID | str) -> None:
        rule = self.get_rule_by_id_or_raise(rule_id)
        # Delete dependent matches first to avoid foreign key issues
        self.db.query(TriggerMatch).filter(TriggerMatch.rule_id == rule.id).delete(
            synchronize_session="fetch"
        )
        self.db.delete(rule)
        self.db.commit()

    # =========================================================================
    # Matching Engine & Post Evaluation
    # =========================================================================

    @staticmethod
    def evaluate_text_match(rule: TriggerRule, text: str) -> tuple[bool, list[str]]:
        r"""
        Hardened keyword evaluation engine:
        Uses lookaround boundaries `(?<!\w)...(?!\w)` instead of `\b...\b`
        so that `#hashtags` and `@mentions` match accurately.
        """
        normalized_text = text.lower()
        matched: list[str] = []

        # 1. Negative Exclusion Check
        for exclude_kw in rule.keywords_exclude:
            pattern = rf"(?<!\w){re.escape(exclude_kw)}(?!\w)"
            if re.search(pattern, normalized_text):
                return False, []

        # 2. Keywords All Check (all must match)
        if rule.keywords_all:
            for all_kw in rule.keywords_all:
                pattern = rf"(?<!\w){re.escape(all_kw)}(?!\w)"
                if not re.search(pattern, normalized_text):
                    return False, []
                matched.append(all_kw)

        # 3. Keywords Any Check (at least one must match)
        if rule.keywords_any:
            any_found = False
            for any_kw in rule.keywords_any:
                pattern = rf"(?<!\w){re.escape(any_kw)}(?!\w)"
                if re.search(pattern, normalized_text):
                    any_found = True
                    matched.append(any_kw)
            if not any_found:
                return False, []

        return True, list(set(matched))

    def evaluate_incoming_post(self, cmd: EvaluateIncomingPostCommand) -> list[TriggerMatch]:
        """
        Evaluates a scraped post against all active rules for the given platform.
        Enforces post deduplication and author cooldown windows.
        """
        rules_query = self.db.query(TriggerRule).filter(
            TriggerRule.platform == cmd.platform,
            TriggerRule.is_active.is_(True),
        )
        if cmd.watched_handle_id:
            rules_query = rules_query.filter(
                (TriggerRule.watched_handle_id == cmd.watched_handle_id)
                | (TriggerRule.watched_handle_id.is_(None))
            )
        else:
            rules_query = rules_query.filter(TriggerRule.watched_handle_id.is_(None))

        active_rules = rules_query.all()
        created_matches: list[TriggerMatch] = []
        now = datetime.now(UTC)

        for rule in active_rules:
            # 1. Post Deduplication Check: Prevent processing identical tweet multiple times
            already_processed = (
                self.db.query(TriggerMatch)
                .filter(
                    TriggerMatch.rule_id == rule.id,
                    TriggerMatch.platform_post_id == cmd.platform_post_id,
                )
                .first()
            )
            if already_processed:
                continue

            # 2. Keyword Evaluation
            is_match, matched_kws = self.evaluate_text_match(rule, cmd.post_content)
            if not is_match:
                continue

            # 3. Anti-Spam Author Cooldown Check
            cooldown_cutoff = now - timedelta(minutes=rule.cooldown_minutes)
            recent_match = (
                self.db.query(TriggerMatch)
                .filter(
                    TriggerMatch.rule_id == rule.id,
                    TriggerMatch.author_handle == cmd.author_handle,
                    TriggerMatch.created_at >= cooldown_cutoff,
                )
                .first()
            )
            if recent_match:
                continue  # Skip author within cooldown window

            # 4. Generate response copy from template
            response_copy: str | None = None
            if rule.response_template:
                response_copy = rule.response_template.replace("{author}", cmd.author_handle)

            match = TriggerMatch(
                rule_id=rule.id,
                watched_handle_id=cmd.watched_handle_id,
                platform_post_id=cmd.platform_post_id,
                platform_post_url=cmd.platform_post_url,
                author_handle=cmd.author_handle,
                post_content=cmd.post_content,
                matched_keywords=matched_kws,
                status=TriggerMatchStatus.PENDING_REVIEW,
                generated_response=response_copy,
            )
            self.db.add(match)
            created_matches.append(match)

        if created_matches:
            self.db.commit()
            for m in created_matches:
                self.db.refresh(m)

        return created_matches

    # =========================================================================
    # Match Review & Actions
    # =========================================================================

    def get_match_by_id(self, match_id: UUID | str) -> TriggerMatch | None:
        target_id = _ensure_uuid(match_id)
        return (
            self.db.query(TriggerMatch)
            .filter(TriggerMatch.id == target_id)
            .first()
        )

    def get_match_by_id_or_raise(self, match_id: UUID | str) -> TriggerMatch:
        match = self.get_match_by_id(match_id)
        if not match:
            raise TriggerMatchNotFoundError(match_id)
        return match

    def list_matches(
        self,
        rule_id: UUID | None = None,
        status: TriggerMatchStatus | None = None,
        limit: int = 50,
    ) -> list[TriggerMatch]:
        query = self.db.query(TriggerMatch).order_by(TriggerMatch.created_at.desc())
        if rule_id is not None:
            query = query.filter(TriggerMatch.rule_id == rule_id)
        if status is not None:
            query = query.filter(TriggerMatch.status == status)
        return query.limit(limit).all()

    def review_match(self, cmd: ReviewMatchCommand) -> TriggerMatch:
        match = self.get_match_by_id_or_raise(cmd.match_id)

        if cmd.status == TriggerMatchStatus.APPROVED:
            match.mark_as_approved(response_text=cmd.edited_response)
        elif cmd.status == TriggerMatchStatus.IGNORED:
            match.mark_as_ignored()

        self.db.commit()
        self.db.refresh(match)
        return match
