from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import create_saz_issue, rate_limit_check
from ..clients.code_agent_client import prepare_and_pr
from ..clients.sanitizer import sanitize
from ..clients.saz_template import render_deployment_saz
from ..schemas import DeploymentWorkflowRequest, DeploymentWorkflowResponse
from ..schemas.issue import SAZIssuePayload

router = APIRouter(prefix="/deployments", tags=["deployments"])


@router.post("/saz-workflow", response_model=DeploymentWorkflowResponse, status_code=201)
async def deployment_saz_workflow(
    body: DeploymentWorkflowRequest,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    # Step 1 — create PR via code-agent-mcp
    pr_title = f"{body.ticket} {body.task} → {body.target.upper()}"
    try:
        pr = prepare_and_pr(
            repo=body.repo,
            branch=body.branch,
            target=body.target,
            ticket=body.ticket,
            title=pr_title,
        )
    except Exception as e:
        log(request_id=rid, user=x_user, action="deployment_saz_workflow",
            input_text=f"repo={body.repo} branch={body.branch} target={body.target}",
            jira_key="SAZ", status="error", error=f"pr: {sanitize(str(e))}")
        raise HTTPException(status_code=502, detail=f"PR creation failed: {sanitize(str(e))}")

    pr_id = pr["pr_id"]
    pr_url = pr.get("pr_url", "")
    aux_branch = pr.get("aux_branch")
    base_branch = pr.get("base_branch") or body.target

    # Step 2 — create SAZ deployment ticket
    znrx_key = body.znrx_key
    try:
        summary, description = render_deployment_saz(
            task=body.task,
            repo=body.repo,
            target=body.target,
            branch=body.branch,
            base_branch=base_branch,
            pr_id=pr_id,
            pr_url=pr_url,
            project_label=body.project_label,
            issue_key=znrx_key,
        )
        payload = SAZIssuePayload(summary=summary, description=description, issue_type="Support")
        saz_key = create_saz_issue(payload, znrx_key=znrx_key)
    except Exception as e:
        log(request_id=rid, user=x_user, action="deployment_saz_workflow",
            input_text=f"repo={body.repo} pr_id={pr_id}",
            jira_key="SAZ", status="partial_error", error=f"saz: {sanitize(str(e))}")
        raise HTTPException(
            status_code=502,
            detail=f"PR created (#{pr_id}) but SAZ failed: {sanitize(str(e))}",
        )

    status = "linked" if znrx_key else "created"
    log(request_id=rid, user=x_user, action="deployment_saz_workflow",
        input_text=f"repo={body.repo} branch={body.branch} target={body.target}",
        jira_key=saz_key, status="ok")

    return DeploymentWorkflowResponse(
        pr_id=pr_id,
        pr_url=pr_url,
        aux_branch=aux_branch,
        saz_key=saz_key,
        summary=summary,
        status=status,
    )
