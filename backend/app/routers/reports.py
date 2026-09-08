from fastapi import APIRouter
router = APIRouter()
@router.post("/export/pdf")
def export_pdf():
    return {"status": "scaffold_stub"}
