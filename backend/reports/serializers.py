from rest_framework import serializers

from reports.models import ReportFile


class ReportFileSerializer(serializers.ModelSerializer):
    period_label = serializers.CharField(source="period.arabic_label", read_only=True)
    file_url = serializers.SerializerMethodField()
    size = serializers.SerializerMethodField()

    class Meta:
        model = ReportFile
        fields = [
            "id",
            "period",
            "period_label",
            "kind",
            "file_url",
            "size",
            "generated_at",
            "emailed_to",
            "emailed_at",
        ]

    def get_file_url(self, obj) -> str | None:
        if not obj.file:
            return None
        request = self.context.get("request")
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url

    def get_size(self, obj) -> int:
        try:
            return obj.file.size
        except (ValueError, OSError):
            return 0
