# Local embedding model. We load it once and reuse it. This turns text into
# vectors for retrieval. It runs on the machine, so it needs no API key and
# stays the same when we switch chat providers.

from sentence_transformers import SentenceTransformer

from app.config import settings

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embed_model)
    return _model


def embed(texts):
    # texts is a list of strings. returns a list of vectors.
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]
