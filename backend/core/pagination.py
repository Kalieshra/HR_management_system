from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 500


class LargePagination(PageNumberPagination):
    """For grids that load a whole month or a whole company at once."""

    page_size = 500
    page_size_query_param = "page_size"
    max_page_size = 2000
