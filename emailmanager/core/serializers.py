from rest_framework import serializers


class DeleteOldEmailsSerializer(serializers.Serializer):
    days_old = serializers.IntegerField(min_value=1)
