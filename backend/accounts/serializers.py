"""Auth and membership serializers."""

from django.contrib.auth import authenticate, password_validation
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from accounts.models import Invitation, Membership, Role, User


class BranchBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name_ar = serializers.CharField()
    name_en = serializers.CharField()


class MembershipSerializer(serializers.ModelSerializer):
    company_id = serializers.IntegerField(source="company.id", read_only=True)
    company_name_ar = serializers.CharField(source="company.name_ar", read_only=True)
    company_name_en = serializers.CharField(source="company.name_en", read_only=True)
    company_slug = serializers.CharField(source="company.slug", read_only=True)
    branches = BranchBriefSerializer(many=True, read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id",
            "company_id",
            "company_name_ar",
            "company_name_en",
            "company_slug",
            "role",
            "branches",
        ]


class UserSerializer(serializers.ModelSerializer):
    memberships = MembershipSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "preferred_language",
            "is_platform_admin",
            "memberships",
        ]
        read_only_fields = ["id", "email", "is_platform_admin"]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"],
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError(_("Incorrect email or password."))
        if not user.is_active:
            raise serializers.ValidationError(_("This account is disabled."))
        attrs["user"] = user
        return attrs


class InvitationSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name_ar", read_only=True)
    is_pending = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invitation
        fields = [
            "id",
            "email",
            "company",
            "company_name",
            "role",
            "expires_at",
            "accepted_at",
            "is_pending",
            "created_at",
        ]
        read_only_fields = ["id", "expires_at", "accepted_at", "created_at"]


class InvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Role.choices)
    branch_ids = serializers.ListField(child=serializers.IntegerField(), required=False)


class AcceptInviteSerializer(serializers.Serializer):
    token = serializers.CharField()
    full_name = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_token(self, value):
        invitation = Invitation.objects.filter(token=value).first()
        if invitation is None:
            raise serializers.ValidationError(_("This invitation link is not valid."))
        if invitation.accepted_at is not None:
            raise serializers.ValidationError(_("This invitation has already been used."))
        if invitation.is_expired:
            raise serializers.ValidationError(_("This invitation has expired."))
        self.context["invitation"] = invitation
        return value

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        invitation = self.context["invitation"]
        user, created = User.objects.get_or_create(
            email=invitation.email,
            defaults={"full_name": validated_data.get("full_name", "")},
        )
        if created or not user.has_usable_password():
            user.set_password(validated_data["password"])
            if validated_data.get("full_name"):
                user.full_name = validated_data["full_name"]
            user.save()

        if invitation.company_id:
            membership, _created = Membership.objects.get_or_create(
                user=user, company=invitation.company, defaults={"role": invitation.role}
            )
        else:
            user.is_platform_admin = True
            user.save(update_fields=["is_platform_admin"])

        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["accepted_at", "updated_at"])
        return user


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("Your current password is incorrect."))
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context["request"].user)
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        password_validation.validate_password(value)
        return value
