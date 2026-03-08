from fastapi import APIRouter, Depends

from ..models import AnalyticsResponse
from ..services.analytics_manager import AnalyticsManager, get_analytics_manager

router = APIRouter()


@router.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(
    manager: AnalyticsManager = Depends(get_analytics_manager),
) -> AnalyticsResponse:
    return manager.get_summary()
