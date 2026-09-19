from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import APIConnectionError, APIStatusError, APITimeoutError

from .approvals import (
    ApprovalError,
    ApprovalRecord,
    EvidenceItem,
    PolicyNotApprovable,
    approve_policy,
    list_approvals,
    list_evidence,
)
from .demo_data import DEMO_POLICY, make_demo_comparison
from .models import (
    NebiusConnectionStatus,
    PolicyApprovalRequest,
    PolicyCompileRequest,
    PolicyCompileResponse,
    PolicyValidationRequest,
    PolicyValidationResponse,
)
from .nebius_client import (
    NebiusConfigurationError,
    available_models,
    compile_policy,
    configured_model,
    has_api_key,
    nvidia_model_candidates,
)
from .policy_validation import validate_policy


app = FastAPI(title="RuleBranch API", version="0.1.0")
logger = logging.getLogger(__name__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "local deterministic demo"}


@app.get("/api/demo/comparison")
def demo_comparison() -> dict[str, Any]:
    return make_demo_comparison().model_dump(mode="json")


@app.post("/api/demo/run/{mode}")
def demo_run(mode: str) -> dict[str, Any]:
    comparison = make_demo_comparison()
    if mode == "baseline":
        return comparison.baseline.model_dump(mode="json")
    if mode == "repair":
        return comparison.repair.model_dump(mode="json")
    raise HTTPException(status_code=404, detail="Run mode must be 'baseline' or 'repair'.")


@app.get("/api/policies/demo")
def demo_policy() -> dict[str, Any]:
    return DEMO_POLICY.model_dump(mode="json")


@app.get("/api/nebius/status", response_model=NebiusConnectionStatus)
def nebius_status() -> NebiusConnectionStatus:
    """Check connectivity by listing models; this does not submit an inference prompt."""
    if not has_api_key():
        return NebiusConnectionStatus(
            configured=False,
            connected=False,
            message="Add NEBIUS_API_KEY to backend/.env and restart the backend.",
        )

    try:
        model_ids = available_models()
    except NebiusConfigurationError as error:
        return NebiusConnectionStatus(configured=False, connected=False, message=str(error))
    except Exception:
        return NebiusConnectionStatus(
            configured=True,
            connected=False,
            message="Token Factory could not be reached. Check the key, account access, and internet connection.",
        )

    candidates = nvidia_model_candidates(model_ids)
    message = (
        "Connected. Choose the recommended NVIDIA model and place its exact identifier in NEBIUS_MODEL."
        if candidates
        else "Connected, but no NVIDIA/Nemotron model was detected. Open Model catalog and contact us before using another model."
    )
    return NebiusConnectionStatus(
        configured=True,
        connected=True,
        message=message,
        model_count=len(model_ids),
        nvidia_model_candidates=candidates,
        recommended_model=candidates[0] if candidates else None,
    )


@app.post("/api/policies/compile", response_model=PolicyCompileResponse)
def compile_policy_endpoint(request: PolicyCompileRequest) -> PolicyCompileResponse:
    """Compile a policy only when the user explicitly invokes this endpoint."""
    if not has_api_key():
        raise HTTPException(
            status_code=503,
            detail=(
                "Nebius Token Factory is not configured yet. Add the key only to backend/.env and restart the backend."
            ),
        )
    try:
        configured_model()
    except NebiusConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
    try:
        policy, model, response_mode = compile_policy(request.policy_text)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except APIStatusError as error:
        # Provider bodies can contain input text or credentials: never log/return them.
        status = error.status_code
        logger.warning("Token Factory rejected policy compilation: HTTP %s", status)
        explanation = {
            400: "The provider rejected the model request. The request parameters need checking.",
            401: "The provider rejected the API key. Check it privately in backend/.env.",
            402: "The provider requires available account credit. Check Token Factory billing.",
            403: "The provider denied access to this model or account.",
            404: "The provider could not find the configured model or endpoint.",
            422: "The provider rejected the request format. This is an integration error, not a reason to replace your API key.",
            429: "The provider reported a rate or quota limit. Check your account limits before retrying.",
        }.get(status, "The provider could not complete the request.")
        raise HTTPException(status_code=502, detail=f"Token Factory HTTP {status}: {explanation}") from None
    except APITimeoutError:
        raise HTTPException(status_code=504, detail="Token Factory timed out. No draft was accepted and no automatic retry was made.") from None
    except APIConnectionError:
        raise HTTPException(status_code=502, detail="The backend could not connect to Token Factory. No draft was accepted.") from None
    except Exception as error:
        logger.error("Token Factory compilation failed: %s", type(error).__name__)
        raise HTTPException(
            status_code=502,
            detail="RuleBranch could not process the response. No draft was accepted; check the backend error type.",
        ) from None
    return PolicyCompileResponse(
        status="compiled",
        message=(
            f"The model returned {response_mode.replace('_', ' ')}; RuleBranch checked the draft's structure and added "
            "local safeguards. Review its meaning before use; no coding task was executed."
        ),
        model=model,
        response_mode=response_mode,
        policy=policy,
    )


@app.post("/api/policies/validate", response_model=PolicyValidationResponse)
def validate_policy_endpoint(request: PolicyValidationRequest) -> PolicyValidationResponse:
    """Evaluate a draft against fixed synthetic calls; execute nothing."""
    return validate_policy(request.policy)


@app.post("/api/policies/approve", response_model=ApprovalRecord)
def approve_policy_endpoint(request: PolicyApprovalRequest) -> ApprovalRecord:
    """Re-check on the server and record an approval. This runs nothing and spends nothing."""
    try:
        return approve_policy(request.policy)
    except PolicyNotApprovable as error:
        raise HTTPException(
            status_code=422,
            detail={"message": str(error), "validation": error.validation.model_dump(mode="json")},
        ) from None
    except ApprovalError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@app.get("/api/approvals", response_model=list[ApprovalRecord])
def approvals_endpoint() -> list[ApprovalRecord]:
    return list_approvals()


@app.get("/api/evidence", response_model=list[EvidenceItem])
def evidence_endpoint() -> list[EvidenceItem]:
    """Read-only: Sandbox evidence the CLI wrote to reports/evidence/."""
    return list_evidence()
