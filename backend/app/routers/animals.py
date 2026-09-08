from fastapi import APIRouter
router = APIRouter()
@router.post("/query")
def query():
    return {"status": "scaffold_stub"}
