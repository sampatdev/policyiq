from sqlalchemy.orm import Session
from app.query import embed_query, search_similar_chunks

# --- Tool schemas: this is what we hand to Claude's API so it knows what's available ---
TOOL_DEFINITIONS = [
    {
        "name": "search_policy_documents",
        "description": "Search insurance policy documents for information about coverage, exclusions, claims process, or terms. Use this whenever the question is about what a policy covers or how it works.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query, e.g. 'knee surgery coverage'"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "calculate_premium_estimate",
        "description": "Calculate an estimated insurance premium given a person's age and desired coverage amount. Use this when the user asks about cost, premium, or pricing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "age": {"type": "integer", "description": "Age of the insured person"},
                "coverage_amount": {"type": "number", "description": "Desired coverage amount in currency units"},
            },
            "required": ["age", "coverage_amount"],
        },
    },
    {
        "name": "check_claim_status",
        "description": "Check the status of an insurance claim given its ID. Use this when the user asks about the status of a specific claim.",
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string", "description": "The ID of the insurance claim, e.g. 'CLM1001'"}
            },
            "required": ["claim_id"],
        },
    },
    {
        "name": "compare_coverage",
        "description": "Compare coverage details between two different insurance policies or coverage queries. Use this when the user wants to understand differences in coverage, exclusions, or terms between two policies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query_a": {"type": "string", "description": "The first coverage query, e.g. 'knee surgery coverage'"},
                "query_b": {"type": "string", "description": "The second coverage query, e.g. 'hip replacement coverage'"},
            },
            "required": ["query_a", "query_b"],
        },
    },
]


MOCK_CLAIMS_DB = {
    "CLM1001": {"status": "Approved", "amount_settled": 45000, "date": "2026-06-15"},
    "CLM1002": {"status": "Under Review", "amount_settled": None, "date": None},
    "CLM1003": {"status": "Rejected", "reason": "Pre-existing condition waiting period not met"},
}

# --- Real implementations: what actually runs when Claude asks for a tool ---

def run_search_policy_documents(db: Session, query: str) -> str:
    query_embedding = embed_query(query)
    chunks = search_similar_chunks(db, query_embedding, top_k=3)
    if not chunks:
        return "No relevant policy information found."
    return "\n\n---\n\n".join(
        f"[From: {row.document_name}]\n{row.chunk_text}" for row in chunks
    )


def run_calculate_premium_estimate(age: int, coverage_amount: float) -> str:
    # Simplified placeholder formula — deterministic, not AI-generated, on purpose.
    base_rate = 0.002
    age_factor = 1 + max(0, (age - 30)) * 0.02
    estimated_premium = coverage_amount * base_rate * age_factor
    return f"Estimated annual premium: {estimated_premium:.2f} for age {age}, coverage {coverage_amount}"


# --- Dispatcher: maps a tool name Claude requests to the function that actually runs it ---
def execute_tool(db: Session, tool_name: str, tool_input: dict) -> str:
    if tool_name == "search_policy_documents":
        return run_search_policy_documents(db, tool_input["query"])
    elif tool_name == "calculate_premium_estimate":
        return run_calculate_premium_estimate(tool_input["age"], tool_input["coverage_amount"])
    elif tool_name == "check_claim_status":
        return run_check_claim_status(tool_input["claim_id"])
    elif tool_name == "compare_coverage":
        return run_compare_coverage(tool_input["query_a"], tool_input["query_b"], db)
    else:
        return f"Unknown tool: {tool_name}"
    

def run_check_claim_status(claim_id: str) -> str:
    claim = MOCK_CLAIMS_DB.get(claim_id.upper())
    if not claim:
        return f"No claim found with ID {claim_id}."
    return str(claim)

def run_compare_coverage(query_a: str, query_b: str, db) -> str:
    result_a = run_search_policy_documents(db, query_a)
    result_b = run_search_policy_documents(db, query_b)
    return f"--- Regarding '{query_a}' ---\n{result_a}\n\n--- Regarding '{query_b}' ---\n{result_b}"