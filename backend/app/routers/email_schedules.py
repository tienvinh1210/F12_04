from fastapi import APIRouter
router = APIRouter()
@router.get("/schedules")
def get_schedules():
    return {"status": "scaffold_stub"}
