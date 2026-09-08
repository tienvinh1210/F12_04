from fastapi import APIRouter
router = APIRouter()
@router.post("/analyze")
def analyze():
    return {"status": "scaffold_stub"}
