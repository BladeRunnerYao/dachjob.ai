from uuid import UUID
from datetime import datetime

from pydantic import BaseModel


class TenantResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}
