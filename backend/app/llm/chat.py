# A thin wrapper around the chat model. We use the OpenAI SDK and point it
# at a base url from config. This works for OpenAI now. Later we can put
# LiteLLM behind these same functions to reach AWS Bedrock without changing
# the callers.

import json

from openai import OpenAI

from app.config import settings

_client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)


def chat(messages, model=None, **kwargs):
    # messages is a list of {"role": ..., "content": ...}.
    # returns the text of the first reply.
    response = _client.chat.completions.create(
        model=model or settings.llm_model,
        messages=messages,
        **kwargs,
    )
    return response.choices[0].message.content


def chat_json(messages, model=None, **kwargs):
    # like chat, but asks the model for a json object and parses it. the
    # prompt should say what shape of json we want.
    response = _client.chat.completions.create(
        model=model or settings.llm_model,
        messages=messages,
        response_format={"type": "json_object"},
        **kwargs,
    )
    return json.loads(response.choices[0].message.content)


def chat_tools(messages, tools, model=None, **kwargs):
    # one step of a tool using loop. the model sees the tools and may reply
    # with tool calls or with plain text. returns the raw message so the
    # caller can run the tools and continue the loop.
    #
    # gpt-6-luna is a reasoning model. to use function tools on the chat
    # completions endpoint it needs reasoning_effort set to none. callers can
    # override this if we move to a model that wants something else.
    kwargs.setdefault("reasoning_effort", "none")
    response = _client.chat.completions.create(
        model=model or settings.llm_model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        **kwargs,
    )
    return response.choices[0].message
