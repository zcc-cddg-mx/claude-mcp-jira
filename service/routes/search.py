from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import build_jql, parse_search_query, rate_limit_check, search_issues
from ..schemas import SearchRequest, SearchResponse

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post("/search", response_model=SearchResponse)
async def search_issues_endpoint(
    body: SearchRequest,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    try:
        struct = parse_search_query(body.query)
        jql, max_results = build_jql(struct)
    except Exception as e:
        log(request_id=rid, user=x_user, action="search_issues", input_text=body.query,
            status="error", error=f"claude: {e}")
        raise HTTPException(status_code=422, detail=f"Query parsing failed: {e}")

    try:
        issues = search_issues(jql, max_results)
    except Exception as e:
        log(request_id=rid, user=x_user, action="search_issues", input_text=body.query,
            claude_payload={"jql": jql}, status="error", error=f"jira: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {e}")

    log(
        request_id=rid,
        user=x_user,
        action="search_issues",
        input_text=body.query,
        claude_payload={"jql": jql},
        status="ok",
    )
    return SearchResponse(total=len(issues), issues=issues)
