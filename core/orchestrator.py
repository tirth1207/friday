import asyncio

from core.agents.runtime import agent_runtime
from providers.nvidia.client import get_model


async def call_nvidia(message: str):

    model = get_model()

    response = await model.ainvoke(
        message
    )

    return response.content


async def ask_friday(message: str):

    # ------------------------------------------------------
    # Run the actual execution workflow
    # ------------------------------------------------------

    await agent_runtime.run_demo_workflow(
        message
    )

    # ------------------------------------------------------
    # Ask Nemotron for the final user-facing response
    # ------------------------------------------------------

    response = await call_nvidia(
        f"""
You are FRIDAY.

The user asked:

{message}

The execution system has completed its analysis.

Give the user a concise, useful response based on the request.

Important:
- Do not pretend you performed tools that were not actually executed.
- Do not expose private chain-of-thought.
- Do not describe hidden reasoning.
- Give a clear final answer.
"""
    )

    return response