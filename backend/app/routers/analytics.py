"""
Роутер аналитики (/api/analytics/*).
Перенесён из analytics-service (порт 4006).
"""
from fastapi import APIRouter, Depends, Response

from app.dependencies import get_admin_user, get_current_user
from app.schemas.analytics import ReportGenerateRequest
from app.services.analytics_service import generate_report, get_stats, upload_to_s3

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/stats/{section}")
def get_stats_section(section: str, user=Depends(get_current_user)):
    """
    Возвращает статистику по разделу.
    Разделы: purchases | payments | reputation | search | summary
    """
    return get_stats(section)


@router.post("/reports/generate")
async def generate_and_upload(data: ReportGenerateRequest, user=Depends(get_admin_user)):
    """Генерирует отчёт и загружает в S3/MinIO. Только для администраторов."""
    from datetime import datetime, timezone
    filename = f"{data.report_type}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.xlsx"
    report_bytes = await generate_report(data.report_type)
    url = await upload_to_s3(report_bytes, filename)
    return {"success": True, "url": url, "filename": filename}


@router.get("/reports/{report_type}/download")
async def download_report(report_type: str, user=Depends(get_current_user)):
    """Скачивает отчёт в формате XLSX напрямую."""
    data = await generate_report(report_type)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={report_type}.xlsx"},
    )
