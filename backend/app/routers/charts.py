from fastapi import APIRouter
router = APIRouter()
@router.post("/timeseries")
def get_timeseries():
    return {"status": "scaffold_stub"}
@router.post("/distribution")
def get_distribution():
    return {"status": "scaffold_stub"}
