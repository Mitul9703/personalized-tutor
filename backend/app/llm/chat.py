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
