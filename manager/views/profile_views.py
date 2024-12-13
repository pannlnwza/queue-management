from django.contrib.auth.mixins import LoginRequiredMixin
from manager.models import Queue, UserProfile
from django.views import generic
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404
from manager.forms import EditProfileForm
from manager.utils.aws_s3_storage import upload_to_s3, get_s3_base_url
from manager.utils.category_handler import CategoryHandlerFactory


class EditProfileView(LoginRequiredMixin, generic.UpdateView):
    """
    View for editing a user's profile, including updating user details and profile image.

    :param model: The UserProfile model for storing the user's profile data.
    :param template_name: The template for rendering the profile edit form.
    :param context_object_name: The name of the context variable for the UserProfile object.
    :param form_class: The form class for editing the profile.

    :return: A redirect to the success URL if the form is valid, or re-renders the form with errors if invalid.
    """

    model = UserProfile
    template_name = 'manager/edit_profile.html'
    context_object_name = 'profile'
    form_class = EditProfileForm

    def get_success_url(self):
        """
        Returns the URL to redirect to after a successful form submission.

        :return: The success URL for the 'edit_profile' view, including the queue_id.
        """
        queue_id = self.kwargs.get('queue_id')
        if queue_id:
            return reverse_lazy('manager:edit_profile', kwargs={'queue_id': queue_id})
        return reverse_lazy('manager:edit_profile_no_queue')

    def get_object(self, queryset=None):
        """
        Retrieves or creates the UserProfile for the currently authenticated user.

        :return: The UserProfile instance for the current user.
        """
        profile, created = UserProfile.objects.get_or_create(
            user=self.request.user)
        return profile

    def form_valid(self, form):
        """
        Handle the update of both the user and their profile, including optional image upload or removal.

        - Updates user details (username, email, first/last name).
        - Updates the associated UserProfile (phone, image, etc.).
        - Handles image removal or upload to S3 if applicable.

        :param form: The submitted form with updated user and profile data.
        :return: A redirect to the success URL if the form is valid.
        """
        user = self.request.user
        user.username = form.cleaned_data['username']
        user.email = form.cleaned_data['email']
        user.first_name = form.cleaned_data.get('first_name',
                                                user.first_name) or ''
        user.last_name = form.cleaned_data.get('last_name',
                                               user.last_name) or ''
        user.save()

        profile = form.save(commit=False)
        profile.user = user
        profile.phone = form.cleaned_data.get('phone', profile.phone)

        # Handle image removal and upload
        if form.cleaned_data.get('remove_image') == 'true':
            profile.image = get_s3_base_url("default_images/profile.jpg")
            profile.google_picture = None
        elif form.files.get('image'):
            try:
                uploaded_file = form.files['image']
                folder = 'profile_images'
                profile.image = upload_to_s3(uploaded_file, folder)
                profile.google_picture = None
            except Exception as e:
                messages.error(self.request, f"Failed to upload image: {e}")
                return self.form_invalid(form)

        profile.save()

        messages.success(self.request, 'Profile updated successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """
        Adds additional context to the template for rendering the profile edit page.

        :return: A dictionary containing the context for the profile edit template, including user profile data,
                 queue-related information, and template base settings.
        """
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        if queue_id:
            queue = get_object_or_404(Queue, id=queue_id)
            handler = CategoryHandlerFactory.get_handler(queue.category)
            queue = handler.get_queue_object(queue_id)
            context['queue'] = queue
            context['queue_id'] = queue_id
            context['base_template'] = 'sidebar_manage.html'
        else:
            context['base_template'] = 'sidebar_home.html'

        context['user'] = self.request.user
        profile = self.get_object()
        context['profile_image_url'] = profile.get_profile_image()
        context['default_image_url'] = get_s3_base_url(
            "default_images/profile.jpg")
        return context
