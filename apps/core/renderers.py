import json
from rest_framework.renderers import JSONRenderer


class EnvelopeRenderer(JSONRenderer):
    """
    Wraps every DRF response in a standarized envelope:

    Success:  {"data": <payload>, "errors": [], "meta": <meta|null>}
    Error:    {"data": null, "errors": [{"message": "..."}], "meta": null}

    If the view already returned an envelope (has 'data' key) it is passed
    through untouched so that paginated views work without double-wrapping.
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get("response") if renderer_context else None
        status_code = response.status_code if response else 200
        is_error = status_code >= 400

        if is_error:
            # Normalise DRF's various error shapes into our envelope
            errors = self._extract_errors(data)
            envelope = {"data": None, "errors": errors, "meta": None}
        elif isinstance(data, dict) and "data" in data and "errors" in data:
            # Already enveloped (e.g. from EnvelopePagination)
            envelope = data
        else:
            envelope = {"data": data, "errors": [], "meta": None}

        return super().render(envelope, accepted_media_type, renderer_context)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_errors(self, data):
        """Convert DRF error dicts/lists into [{"message": "..."}]."""
        if data is None:
            return [{"message": "An unexpected error occurred."}]

        if isinstance(data, list):
            return [{"message": self._stringify(item)} for item in data]

        if isinstance(data, dict):
            messages = []
            for key, value in data.items():
                if key == "detail":
                    messages.append({"message": str(value)})
                elif isinstance(value, list):
                    for v in value:
                        label = "" if key == "non_field_errors" else f"{key}: "
                        messages.append({"message": f"{label}{self._stringify(v)}"})
                else:
                    messages.append({"message": f"{key}: {self._stringify(value)}"})
            return messages or [{"message": str(data)}]

        return [{"message": str(data)}]

    def _stringify(self, value):
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)
