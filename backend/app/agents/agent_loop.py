# The shared tool loop that every agent runs on. The caller gives a system
# prompt, a first user message, the tools, and handlers for them. The model
# drives: it calls tools, reads the results, and calls finish when it is
# done. max_steps is only a safety fuse so a stuck loop cannot run forever.
# All the real decisions (what to call, when to stop) are the model's.

import json

from app.llm.chat import chat_tools


def run_agent(system, user, tools, handlers, max_steps=6):
    # tools: the OpenAI tool schemas (must include a finish tool).
    # handlers: {tool_name: fn(args) -> dict}. finish is handled here.
    # returns the args the model passed to finish, or {"_text": ...} if the
    # model stopped with plain text instead of calling finish.
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    result = {}
    for _ in range(max_steps):
        message = chat_tools(messages, tools)
        messages.append(message)

        if not message.tool_calls:
            result = {"_text": message.content}
            break

        stop = False
        for call in message.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if name == "finish":
                result = args
                out = {"ok": True}
                stop = True
            else:
                handler = handlers.get(name)
                out = handler(args) if handler else {"ok": False, "error": f"unknown tool {name}"}

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(out),
            })

        if stop:
            break

    return result
