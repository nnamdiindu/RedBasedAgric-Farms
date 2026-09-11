from urllib.parse import urlencode


def make_query_builder(base_params: dict):
    """Return a callable that renders a query string from base_params,
    with keyword overrides layered on top. Falsy/None values are dropped
    so links don't accumulate empty params."""

    def build(**overrides):
        params = {**base_params, **overrides}
        params = {k: v for k, v in params.items() if v not in (None, "", False)}
        return urlencode(params)

    return build
