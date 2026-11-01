from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.common.enums import CampaignStatus, PostStatus
from app.modules.accounts.exceptions import AccountNotFoundError
from app.modules.accounts.models import ConnectedAccount
from app.modules.campaigns.commands import (
    CreateCampaignCommand,
    QueuePostCommand,
    RecordPostDeliveryCommand,
    RecordPostFailureCommand,
    UpdateCampaignCommand,
    UpdatePostCommand,
)
from app.modules.campaigns.exceptions import (
    CampaignInactiveError,
    CampaignNotFoundError,
    InvalidPostScheduleError,
    PostAlreadyPublishedError,
    PostNotFoundError,
)
from app.modules.campaigns.models import Campaign, ScheduledPost


def _ensure_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


class CampaignService:
    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # Campaign Queries & Mutations
    # =========================================================================

    def get_campaign_by_id(self, campaign_id: UUID | str) -> Campaign | None:
        """Fetch a single campaign with eager-loaded posts, returning None if not found."""
        target_id = _ensure_uuid(campaign_id)
        return (
            self.db.query(Campaign)
            .options(selectinload(Campaign.posts))
            .filter(Campaign.id == target_id)
            .first()
        )

    def get_campaign_by_id_or_raise(self, campaign_id: UUID | str) -> Campaign:
        """Fetch a campaign by ID or raise CampaignNotFoundError."""
        campaign = self.get_campaign_by_id(campaign_id)
        if not campaign:
            raise CampaignNotFoundError(campaign_id)
        return campaign

    def list_campaigns(self, status: CampaignStatus | None = None) -> list[Campaign]:
        """List all campaigns, optionally filtering by lifecycle status."""
        query = self.db.query(Campaign).order_by(Campaign.created_at.desc())
        if status is not None:
            query = query.filter(Campaign.status == status)
        return query.all()

    def create_campaign(self, cmd: CreateCampaignCommand) -> Campaign:
        """Persist a new marketing campaign."""
        campaign = Campaign(
            name=cmd.name,
            description=cmd.description,
            target_audience=cmd.target_audience,
            status=cmd.status,
            start_date=cmd.start_date,
            end_date=cmd.end_date,
            tags=cmd.tags,
            extra_metadata=cmd.extra_metadata,
        )
        self.db.add(campaign)
        self.db.commit()
        self.db.refresh(campaign)
        return campaign

    def update_campaign(self, cmd: UpdateCampaignCommand) -> Campaign:
        """Update campaign metadata or status."""
        campaign = self.get_campaign_by_id_or_raise(cmd.campaign_id)

        if cmd.name is not None:
            campaign.name = cmd.name
        if cmd.description is not None:
            campaign.description = cmd.description
        if cmd.target_audience is not None:
            campaign.target_audience = cmd.target_audience
        if cmd.status is not None:
            campaign.status = cmd.status
        if cmd.start_date is not None:
            campaign.start_date = cmd.start_date
        if cmd.end_date is not None:
            campaign.end_date = cmd.end_date
        if cmd.tags is not None:
            campaign.tags = cmd.tags
        if cmd.extra_metadata is not None:
            campaign.extra_metadata = cmd.extra_metadata

        self.db.commit()
        self.db.refresh(campaign)
        return campaign

    def delete_campaign(self, campaign_id: UUID | str) -> None:
        """Remove a campaign and cascade delete its scheduled posts."""
        campaign = self.get_campaign_by_id_or_raise(campaign_id)
        self.db.delete(campaign)
        self.db.commit()

    # =========================================================================
    # Scheduled Post Queries & Lifecycle Mutations
    # =========================================================================

    def get_post_by_id(self, post_id: UUID | str) -> ScheduledPost | None:
        """Fetch a single scheduled post, returning None if not found."""
        target_id = _ensure_uuid(post_id)
        return (
            self.db.query(ScheduledPost)
            .filter(ScheduledPost.id == target_id)
            .first()
        )

    def get_post_by_id_or_raise(self, post_id: UUID | str) -> ScheduledPost:
        """Fetch a single post or raise PostNotFoundError."""
        post = self.get_post_by_id(post_id)
        if not post:
            raise PostNotFoundError(post_id)
        return post

    def list_posts_by_campaign(
        self, campaign_id: UUID | str, status: PostStatus | None = None
    ) -> list[ScheduledPost]:
        """List all posts linked to a specific campaign."""
        target_id = _ensure_uuid(campaign_id)
        self.get_campaign_by_id_or_raise(target_id)

        query = (
            self.db.query(ScheduledPost)
            .filter(ScheduledPost.campaign_id == target_id)
            .order_by(ScheduledPost.scheduled_at.asc(), ScheduledPost.created_at.asc())
        )
        if status is not None:
            query = query.filter(ScheduledPost.status == status)
        return query.all()

    def get_due_posts(self, limit: int = 50) -> list[ScheduledPost]:
        """
        Poll query utilized by the background post dispatcher worker.
        Fetches pending posts scheduled on or before the current timestamp.
        """
        now = datetime.now(UTC)
        return (
            self.db.query(ScheduledPost)
            .filter(
                ScheduledPost.status == PostStatus.SCHEDULED,
                ScheduledPost.scheduled_at <= now,
            )
            .order_by(ScheduledPost.scheduled_at.asc())
            .limit(limit)
            .all()
        )

    def queue_post(self, cmd: QueuePostCommand) -> ScheduledPost:
        """
        Stages or schedules an outbound post after validating campaign
        state, date boundaries, and account existence.
        """
        campaign = self.get_campaign_by_id_or_raise(cmd.campaign_id)

        if campaign.status in (CampaignStatus.ARCHIVED, CampaignStatus.COMPLETED):
            raise CampaignInactiveError(campaign.id, campaign.status.value)

        # Verify connected account exists
        account = (
            self.db.query(ConnectedAccount)
            .filter(ConnectedAccount.id == cmd.account_id)
            .first()
        )
        if not account:
            raise AccountNotFoundError(cmd.account_id)

        # Validate schedule lies within campaign boundaries if defined
        if cmd.scheduled_at:
            scheduled_utc = (
                cmd.scheduled_at.replace(tzinfo=UTC)
                if cmd.scheduled_at.tzinfo is None
                else cmd.scheduled_at
            )
            if campaign.end_date:
                end_utc = (
                    campaign.end_date.replace(tzinfo=UTC)
                    if campaign.end_date.tzinfo is None
                    else campaign.end_date
                )
                if scheduled_utc > end_utc:
                    raise InvalidPostScheduleError(
                        f"Post schedule time ({scheduled_utc.isoformat()}) exceeds "
                        f"campaign end date ({end_utc.isoformat()})."
                    )

        post = ScheduledPost(
            campaign_id=cmd.campaign_id,
            account_id=cmd.account_id,
            content=cmd.content,
            content_type=cmd.content_type,
            media_urls=cmd.media_urls,
            scheduled_at=cmd.scheduled_at,
            status=cmd.status,
            max_retries=cmd.max_retries,
            extra_metadata=cmd.extra_metadata,
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def update_post(self, cmd: UpdatePostCommand) -> ScheduledPost:
        """Updates a post copy, media, or schedule before dispatch."""
        post = self.get_post_by_id_or_raise(cmd.post_id)

        if post.status == PostStatus.PUBLISHED:
            raise PostAlreadyPublishedError(post.id)

        if cmd.account_id is not None:
            account = (
                self.db.query(ConnectedAccount)
                .filter(ConnectedAccount.id == cmd.account_id)
                .first()
            )
            if not account:
                raise AccountNotFoundError(cmd.account_id)
            post.account_id = cmd.account_id

        if cmd.content is not None:
            post.content = cmd.content
        if cmd.content_type is not None:
            post.content_type = cmd.content_type
        if cmd.media_urls is not None:
            post.media_urls = cmd.media_urls
        if cmd.scheduled_at is not None:
            post.scheduled_at = cmd.scheduled_at
        if cmd.status is not None:
            post.status = cmd.status
        if cmd.extra_metadata is not None:
            post.extra_metadata = cmd.extra_metadata

        self.db.commit()
        self.db.refresh(post)
        return post

    def cancel_post(self, post_id: UUID | str) -> ScheduledPost:
        """Transitions a scheduled post into CANCELLED state."""
        post = self.get_post_by_id_or_raise(post_id)
        if post.status == PostStatus.PUBLISHED:
            raise PostAlreadyPublishedError(post.id)

        post.status = PostStatus.CANCELLED
        self.db.commit()
        self.db.refresh(post)
        return post

    def delete_post(self, post_id: UUID | str) -> None:
        """Permanently removes a draft or cancelled post."""
        post = self.get_post_by_id_or_raise(post_id)
        if post.status == PostStatus.PUBLISHED:
            raise PostAlreadyPublishedError(post.id)

        self.db.delete(post)
        self.db.commit()

    def record_delivery(self, cmd: RecordPostDeliveryCommand) -> ScheduledPost:
        """Mark post as PUBLISHED upon confirmation from platform adapter."""
        post = self.get_post_by_id_or_raise(cmd.post_id)
        post.mark_as_published(
            post_id=cmd.platform_post_id,
            post_url=cmd.platform_post_url,
        )
        self.db.commit()
        self.db.refresh(post)
        return post

    def record_failure(self, cmd: RecordPostFailureCommand) -> ScheduledPost:
        """Records platform error and triggers retry or transitions to FAILED."""
        post = self.get_post_by_id_or_raise(cmd.post_id)
        post.mark_as_failed(error=cmd.error_message)
        self.db.commit()
        self.db.refresh(post)
        return post
