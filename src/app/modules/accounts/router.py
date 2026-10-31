from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.modules.accounts.schemas import (
    AccountCreateRequest,
    AccountResponse,
    AccountUpdateRequest,
)
from app.modules.accounts.service import AccountService

router = APIRouter()


def get_account_service(db: Session = Depends(get_db_session)) -> AccountService:
    """Dependency injection factory for AccountService."""
    return AccountService(db)


@router.post(
    "/",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a new social or email account",
)
def create_account(
    payload: AccountCreateRequest,
    service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    account = service.create_account(payload.to_command())
    return AccountResponse.model_validate(account)


@router.get(
    "/",
    response_model=list[AccountResponse],
    status_code=status.HTTP_200_OK,
    summary="List all connected accounts",
)
def list_accounts(
    active_only: bool = Query(
        default=False,
        description="If true, returns only enabled/active accounts",
    ),
    service: AccountService = Depends(get_account_service),
) -> list[AccountResponse]:
    accounts = service.list_accounts(active_only=active_only)
    return [AccountResponse.model_validate(acc) for acc in accounts]


@router.get(
    "/{account_id}",
    response_model=AccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a connected account by ID",
)
def get_account(
    account_id: UUID,
    service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    account = service.get_by_id_or_raise(account_id)
    return AccountResponse.model_validate(account)


@router.patch(
    "/{account_id}",
    response_model=AccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Update account settings, limits, or rotate credentials",
)
def update_account(
    account_id: UUID,
    payload: AccountUpdateRequest,
    service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    account = service.update_account(payload.to_command(account_id))
    return AccountResponse.model_validate(account)


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect and delete an account",
)
def delete_account(
    account_id: UUID,
    service: AccountService = Depends(get_account_service),
) -> None:
    service.delete_account(account_id)
