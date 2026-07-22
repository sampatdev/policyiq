from sqlalchemy.orm import Session
import anthropic

from app.config import settings
from app.tools import TOOL_DEFINITIONS, execute_tool

claude_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def run_agent(db: Session, user_question: str) -> dict:
    messages = [{"role": "user", "content": user_question}]
    tool_calls_made = []  # we track this so we can show/inspect what the agent decided to do

    while True:
        response = claude_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=800,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            # Claude gave a final text answer — we're done looping
            final_text = "".join(block.text for block in response.content if block.type == "text")
            return {"answer": final_text, "tool_calls": tool_calls_made}

        # Claude wants to call one or more tools — append its request to the conversation
        messages.append({"role": "assistant", "content": response.content})

        # Run each requested tool and collect the results
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_text = execute_tool(db, block.name, block.input)
                tool_calls_made.append({"tool": block.name, "input": block.input})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })

        # Send the tool results back so Claude can decide what to do next
        messages.append({"role": "user", "content": tool_results})