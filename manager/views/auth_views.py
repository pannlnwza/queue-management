import logging
import json
from django.shortcuts import render, redirect
from django.contrib import messages
from django.dispatch import receiver
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, user_logged_in, \
    user_logged_out, user_login_failed
from manager.forms import CustomUserCreationForm
from manager.models import UserProfile

logger = logging.getLogger('queue')


def signup(request):
    """
    Register a new user and create a profile.

    Handles user registration and profile creation. If the form is valid, it creates a new user, logs them in, and redirects them to the home page.
    If the form is invalid, it re-renders the signup page with error messages.

    :return: A redirect to the home page on successful signup, or re-renders the signup form if validation fails.
    """
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            raw_passwd = form.cleaned_data.get('password1')

            profile, created = UserProfile.objects.get_or_create(user=user)
            if not profile:
                messages.error(request,
                               'Error creating user profile. Please contact support.')

            user = authenticate(username=username, password=raw_passwd)
            if user is not None:
                login(request, user)
                logger.info(f'New user signed up with profile: {username}')
                return redirect('participant:home')
            else:
                logger.error(
                    f'Failed to authenticate user after signup: {username}')
                messages.error(request,
                               'Error during signup process. Please try again.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    logger.error(f'Error signup: {error}')

    else:
        form = CustomUserCreationForm()

    return render(request, 'account/signup.html', {'form': form})


def login_view(request):
    """
    Handle user login and update profile if needed.

    Authenticates the user with the provided username and password. If successful, logs the user in, updates their profile with a Google profile image (if available), and redirects to the 'your-queue' page. If authentication fails, it displays an error message.

    :return: A redirect to the 'your-queue' page on successful login, or re-renders the login page with an error message if login fails.
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            profile, created = UserProfile.objects.get_or_create(user=user)

            # Simplify social account image retrieval
            social_accounts = user.socialaccount_set.filter(provider='google')
            if social_accounts.exists():
                extra_data = social_accounts.first().extra_data
                profile_image_url = extra_data.get('picture')
                if profile_image_url:
                    profile.google_picture = profile_image_url
                    profile.save()
                    logger.info(
                        f'Google profile image updated for user: {username}')

            return redirect('manager:your-queue')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'account/login.html')


@csrf_exempt
def set_location(request):
    """
    Set the user's location to display nearby queues.

    This view accepts a POST request with latitude and longitude data in JSON format, stores it in the user's session, and returns a success response. If the data is invalid or the method is not POST, an error response is returned.

    :return: JsonResponse with a success or failure status.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lat = data.get('lat')
            lon = data.get('lon')
            if lat and lon:
                # Store latitude and longitude in the session
                request.session['user_lat'] = lat
                request.session['user_lon'] = lon
                print(f"Saved to session: Lat = {lat}, Lon = {lon}")
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse(
                    {'status': 'failed', 'error': 'Invalid data'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'failed', 'error': 'Invalid JSON'},
                                status=400)
    return JsonResponse(
        {'status': 'failed', 'error': 'Only POST method allowed'}, status=400)


def get_client_ip(request):
    """
    Retrieve the client's IP address from the request.

    This function checks the `HTTP_X_FORWARDED_FOR` header first (for proxied requests) and falls back to `REMOTE_ADDR` if not available.

    :return: The client's IP address as a string.
    """
    return (
        x_forwarded_for.split(',')[0]
        if (x_forwarded_for := request.META.get('HTTP_X_FORWARDED_FOR'))
        else request.META.get('REMOTE_ADDR'))


@receiver(user_logged_in)
def user_login(request, user, **kwargs):
    """Log a message when a user logs in."""
    ip = get_client_ip(request)
    logger.info(f"User {user.username} logged in from {ip}")


@receiver(user_logged_out)
def user_logout(request, user, **kwargs):
    """Log a message when a user logs out."""
    ip = get_client_ip(request)
    logger.info(f"User {user.username} logged out from {ip}")


@receiver(user_login_failed)
def user_login_failed(credentials, request, **kwargs):
    """Log a message when a user login attempt fails."""
    ip = get_client_ip(request)
    logger.warning(f"Failed login attempt for user "
                   f"{credentials.get('username')} from {ip}")