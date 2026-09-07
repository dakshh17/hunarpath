"""
ShilpSetu – Authentication router.

Endpoints for artisan login and registration using phone + PIN.
"""

from __future__ import annotations

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_session
from models import Artisan, Cluster
from schemas import (
    ArtisanProfileResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
)
from services.auth_service import create_access_token, hash_pin, verify_pin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


def _build_profile(artisan: Artisan, cluster_name: str) -> ArtisanProfileResponse:
    return ArtisanProfileResponse(
        id=artisan.id,
        name=artisan.name,
        phone=artisan.phone,
        cluster_id=artisan.cluster_id,
        cluster_name=cluster_name,
        dialect=artisan.native_dialect,
        rating=artisan.rating,
        verified=artisan.verification_status,
    )


@router.post("/login", response_model=LoginResponse, summary="Artisan phone+PIN login")
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate an artisan with phone number and PIN."""
    stmt = (
        select(Artisan)
        .where(Artisan.phone == body.phone)
        .options(selectinload(Artisan.cluster))
    )
    result = await session.execute(stmt)
    artisan = result.scalar_one_or_none()

    if artisan is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phone number not registered.",
        )

    if not artisan.pin_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No PIN set for this account. Please contact support.",
        )

    if not verify_pin(body.pin, artisan.pin_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect PIN.",
        )

    token = create_access_token(artisan.id)
    cluster_name = artisan.cluster.name if artisan.cluster else "Unknown"

    return LoginResponse(
        token=token,
        artisan=_build_profile(artisan, cluster_name),
    )


@router.post("/register", response_model=LoginResponse, summary="Register a new artisan")
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """Register a new artisan and return a JWT token."""
    # Check phone uniqueness
    existing = await session.execute(
        select(Artisan).where(Artisan.phone == body.phone)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone number already registered.",
        )

    # Validate cluster exists
    cluster = await session.get(Cluster, body.cluster_id)
    if cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found.",
        )

    artisan = Artisan(
        id=uuid.uuid4().hex,
        cluster_id=body.cluster_id,
        name=body.name,
        native_dialect=body.dialect,
        phone=body.phone,
        rating=4.8,
        verification_status=True,
        daily_wage_baseline=body.daily_wage,
        pin_hash=hash_pin(body.pin),
    )
    session.add(artisan)
    await session.flush()

    token = create_access_token(artisan.id)

    return LoginResponse(
        token=token,
        artisan=_build_profile(artisan, cluster.name),
    )
