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
    model = UserProfile
    template_name = 'manager/edit_profile.html'
    context_object_name = 'profile'
    form_class = EditProfileForm

    def get_success_url(self):
        queue_id = self.kwargs.get('queue_id')
        return reverse_lazy('manager:edit_profile',
                            kwargs={'queue_id': queue_id})

    def get_object(self, queryset=None):
        profile, created = UserProfile.objects.get_or_create(
            user=self.request.user)
        return profile

    def form_valid(self, form):
        """Handle both User and UserProfile updates"""
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
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)
        handler = CategoryHandlerFactory.get_handler(queue.category)
        queue = handler.get_queue_object(queue_id)
        context['queue'] = queue
        context['queue_id'] = queue_id
        context['user'] = self.request.user
        profile = self.get_object()
        context['profile_image_url'] = profile.get_profile_image()
        context['default_image_url'] = get_s3_base_url(
            "default_images/profile.jpg")
        return context