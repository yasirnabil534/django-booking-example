from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class EnvelopePagination(PageNumberPagination):
    """
    Standard paginator that produces envelope-compatible meta block.
    Response is assembled by EnvelopeRenderer; this class just exposes
    the helper method used by views to build the meta dict.
    """
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            "data": data,
            "errors": [],
            "meta": self.get_meta(),
        })

    def get_meta(self):
        return {
            "page": self.page.number,
            "total_pages": self.page.paginator.num_pages,
            "total_count": self.page.paginator.count,
        }

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "data": schema,
                "errors": {"type": "array", "items": {}},
                "meta": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer"},
                        "total_pages": {"type": "integer"},
                        "total_count": {"type": "integer"},
                    },
                },
            },
        }
