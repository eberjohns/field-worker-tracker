"""API endpoints for bulk workbook imports."""

import email
from email import policy
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.identity import User, require_role
from fw.modules.imports import (
    ImportBatch,
    ImportBatchRead,
    ImportCommitResponse,
    ImportPreviewResponse,
    ImportRollbackResponse,
    ImportRow,
    ImportRowRead,
    ImportService,
    generate_import_template_bytes,
)

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("/template")
async def download_import_template(
    current_user: User = Depends(require_role("ADMIN")),
) -> Response:
    """Download the generated master data import template workbook."""
    content = generate_import_template_bytes()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=FieldWorkerTracker_Import_Template_v1.0.xlsx"
        },
    )


@router.post("", response_model=ImportPreviewResponse, status_code=status.HTTP_201_CREATED)
async def upload_workbook(
    request: Request,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> ImportPreviewResponse:
    """Upload workbook (multipart or raw bytes) and return safe preview with field-level diffs without committing."""
    content_type = request.headers.get("content-type", "")
    body = await request.body()

    if not body or len(body) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "EMPTY_FILE", "message": "Uploaded file is empty."},
        )

    filename = "uploaded_workbook.xlsx"
    file_bytes: bytes = body

    if "multipart/form-data" in content_type:
        msg = email.message_from_bytes(
            f"Content-Type: {content_type}\r\n\r\n".encode() + body, policy=policy.default
        )
        found_file = False
        for part in msg.iter_parts():
            fn = part.get_filename()
            if fn:
                filename = fn
                raw_payload = part.get_payload(decode=True)
                if isinstance(raw_payload, bytes):
                    file_bytes = raw_payload
                elif isinstance(raw_payload, str):
                    file_bytes = raw_payload.encode()
                else:
                    file_bytes = b""
                found_file = True
                break
        if not found_file or len(file_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "EMPTY_FILE",
                    "message": "No valid file found in multipart upload.",
                },
            )

    if not (filename.endswith(".xlsx") or filename.endswith(".xlsm")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_FILE_TYPE", "message": "Only .xlsx workbooks are supported."},
        )

    preview = await ImportService.parse_and_preview(
        session=session,
        file_bytes=file_bytes,
        filename=filename,
        user_id=current_user.id,
    )
    return preview


@router.get("/{batch_id}/preview", response_model=ImportPreviewResponse)
async def get_import_preview(
    batch_id: UUID,
    sheet: str | None = None,
    row_status: str | None = None,
    action: str | None = None,
    limit: int = 200,
    offset: int = 0,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> ImportPreviewResponse:
    """Get preview details, counts, and filtered rows for an import batch."""
    b_stmt = select(ImportBatch).where(ImportBatch.id == batch_id)
    batch = (await session.execute(b_stmt)).scalar_one_or_none()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Import batch {batch_id} not found."},
        )

    stmt = select(ImportRow).where(ImportRow.batch_id == batch_id)
    if sheet:
        stmt = stmt.where(ImportRow.sheet == sheet)
    if row_status:
        stmt = stmt.where(ImportRow.status == row_status.upper())
    if action:
        stmt = stmt.where(ImportRow.action == action.upper())

    stmt = (
        stmt.order_by(ImportRow.sheet.asc(), ImportRow.row_number.asc()).offset(offset).limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()

    can_commit = batch.summary.get("can_commit", False)
    return ImportPreviewResponse(
        batch_id=batch.id,
        filename=batch.filename,
        template_version=batch.template_version,
        status=batch.status,
        can_commit=can_commit,
        summary=batch.summary,
        rows=[ImportRowRead.model_validate(r) for r in rows],
    )


@router.post("/{batch_id}/commit", response_model=ImportCommitResponse)
async def commit_import_batch(
    batch_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> ImportCommitResponse:
    """Commit an uploaded and previewed import batch in a single atomic transaction."""
    try:
        res = await ImportService.commit_batch(
            session=session,
            batch_id=batch_id,
            user_id=current_user.id,
            actor_role=current_user.role,
        )
        return res
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "COMMIT_REJECTED", "message": str(e)},
        ) from e


@router.post("/{batch_id}/rollback", response_model=ImportRollbackResponse)
async def rollback_import_batch(
    batch_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> ImportRollbackResponse:
    """Rollback a committed import batch if safe."""
    try:
        res = await ImportService.rollback_batch(
            session=session,
            batch_id=batch_id,
            user_id=current_user.id,
            actor_role=current_user.role,
        )
        return res
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ROLLBACK_FAILED", "message": str(e)},
        ) from e


@router.get("/{batch_id}/errors.xlsx")
async def download_error_report(
    batch_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Download an Excel report of errors and warnings for a batch."""
    b_stmt = select(ImportBatch).where(ImportBatch.id == batch_id)
    batch = (await session.execute(b_stmt)).scalar_one_or_none()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Import batch {batch_id} not found."},
        )

    content = await ImportService.export_errors_xlsx(session, batch_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=errors_{batch.filename}"},
    )


@router.get("", response_model=list[ImportBatchRead])
async def list_import_batches(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> list[ImportBatchRead]:
    """List history of past import batches."""
    stmt = select(ImportBatch).order_by(ImportBatch.created_at.desc()).offset(offset).limit(limit)
    res = await session.execute(stmt)
    batches = res.scalars().all()
    return [ImportBatchRead.model_validate(b) for b in batches]
