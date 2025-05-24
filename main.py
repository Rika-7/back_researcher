from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session
from database import get_db, engine, Base
import models

app = FastAPI(title="Research API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app-advanced3-4-aygnfjh3hxbyducf.canadacentral-01.azurewebsites.net",
        "http://localhost:3000",
        "http://0.0.0.0:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"Hello": "World"}


# Researcher取得
@app.get("/researchers", tags=["Researchers"])
def get_researchers(db: Session = Depends(get_db)):
    researchers = db.query(models.ResearcherInformation).limit(10).all()
    result = []
    for r in researchers:
        result.append({
            "researcher_id": r.researcher_id,
            "researcher_name": r.researcher_name,
            "position": r.researcher_position_current,
            "research_field": r.research_field_pi,
            "keywords": r.keywords_pi,
        })
    return {"status": "success", "researchers": result}


@app.get("/search-researcher")
def search_researcher(name: str, db: Session = Depends(get_db)):
    researchers = db.query(models.ResearcherInformation).filter(
        models.ResearcherInformation.researcher_name.ilike(f"%{name}%")
    ).all()

    if not researchers:
        return {"status": "not_found"}

    return {
        "status": "success",
        "researchers": [
            {
                "researcher_id": r.researcher_id,
                "researcher_name": r.researcher_name,
                "researcher_affiliation_current": r.researcher_affiliation_current,
                "researcher_department_current": r.researcher_department_current,
            }
            for r in researchers
        ]
    }

@app.get("/matching-information", tags=["Matching"])
def get_matching(
    researcher_id: int = Query(..., description="研究者ID"),
    matching_status: int = Query(..., description="マッチングステータス"),
    db: Session = Depends(get_db)
):
    matchings = db.query(models.MatchingInformation).filter(
        models.MatchingInformation.researcher_id == researcher_id,
        models.MatchingInformation.matching_status == matching_status
    ).all()

    result = []
    for m in matchings:
        result.append({
            "matching_id": m.matching_id,
            "project_id": m.project_id,
            "researcher_id": m.researcher_id,
            #"matching_reason":m.matching_reason,
            "project_title": m.project.project_title,
            "consultation_category": m.project.consultation_category,
            "project_content": m.project.project_content,
            "research_field": m.project.research_field,
            #"project_status": m.project.project_status,
            "application_deadline": m.project.application_deadline,
            "budget": m.project.budget,
            #"preferred_researcher_level": m.project.preferred_researcher_level,
            "company_user_name": m.project.company_user.company_user_name if m.project and m.project.company_user else None,
            "department": m.project.company_user.department if m.project and m.project.company_user else None,
            "company_name": m.project.company_user.company.company_name if m.project and m.project.company_user and m.project.company_user.company else None,
        })

    return {"status": "success", "projects": result, "total": len(result)}

@app.get("/matching-id/{matching_id}", tags=["Matching"])
def get_project_by_id(
    matching_id: int,
    db: Session = Depends(get_db)
):
    matching = db.query(models.MatchingInformation).filter(
        models.MatchingInformation.matching_id == matching_id
    ).first()

    if not matching:
        raise HTTPException(status_code=404, detail="Project not found")

    project = matching.project
    company_user = project.company_user if project else None
    company = company_user.company if company_user else None

    result = {
        "matching_id": matching.matching_id,
        "project_id": matching.project_id,
        "researcher_id": matching.researcher_id,
        "matching_status": matching.matching_status,
        "matched_date": matching.matched_date,
        #"matching_reason": matching.matching_reason,
        "project_title": project.project_title if project else None,
        "consultation_category": project.consultation_category if project else None,
        "project_content": project.project_content if project else None,
        "research_field": project.research_field if project else None,
        #"project_status": project.project_status if project else None,
        "application_deadline": project.application_deadline if project else None,
        "budget": project.budget if project else None,
        #"preferred_researcher_level": project.preferred_researcher_level if project else None,
        "company_user_name": company_user.company_user_name if company_user else None,
        "department": company_user.department if company_user else None,
        "company_name": company.company_name if company else None
    }

    return {"status": "success", "project": result}


@app.patch("/matching-status/{matching_id}", tags=["Matching"])
def update_matching_status(
    matching_id: int,
    new_status: int = Query(..., description="新しいマッチングステータス"),
    db: Session = Depends(get_db)
):
    matching = db.query(models.MatchingInformation).filter(
        models.MatchingInformation.matching_id == matching_id
    ).first()

    if not matching:
        raise HTTPException(status_code=404, detail="Matching not found")

    matching.matching_status = new_status
    db.commit()
    db.refresh(matching)

    return {"status": "success", "matching_id": matching_id, "new_status": new_status}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)