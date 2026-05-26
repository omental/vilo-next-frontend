from fastapi import APIRouter, Depends

from app.api.deps import get_current_organization
from app.models.organization import Organization
from app.schemas.organization import OrganizationOut

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/me", response_model=OrganizationOut)
async def organization_me(org: Organization = Depends(get_current_organization)):
    return OrganizationOut(
        id=org.id,
        name=org.name,
        slug=org.slug,
        status=org.status.value,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )
