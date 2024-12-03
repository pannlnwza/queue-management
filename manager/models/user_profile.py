from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from manager.utils.aws_s3_storage import get_s3_base_url


class UserProfile(models.Model):
    """Represents a user profile in the system."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='profile_images/', blank=True,
                              null=True, max_length=255)
    google_picture = models.URLField(blank=True, null=True)
    phone = models.CharField(max_length=10, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    first_name = models.CharField(max_length=30, blank=True, null=True)
    last_name = models.CharField(max_length=30, blank=True, null=True)

    def get_profile_image(self):
        """
        Returns the profile image URL.

        Checks for a user’s profile image or a linked social account avatar,
        otherwise returns a default image.

        :return: The URL of the profile image.
        """
        default_image_url = get_s3_base_url('default_images/profile.jpg')
        if self.image:
            return self.image
        elif self.user.socialaccount_set.exists():
            social_account = self.user.socialaccount_set.first()
            if hasattr(social_account,
                       'get_avatar_url') and social_account.get_avatar_url():
                return social_account.get_avatar_url()
        return default_image_url


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create a UserProfile when a new User is created.
    """
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Automatically save the UserProfile when the User is saved.
    """
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)
