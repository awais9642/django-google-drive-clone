from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import CreateView, UpdateView
from django.urls import reverse_lazy

from .forms import RegisterForm , ProfileUpdateForm
from .models import User


class RegisterView(CreateView):
    """
    Handles new user sign-up. On success, logs the user in immediately
    and sends them to the drive home page — no need to make them log in
    again right after registering.
    """
    model = User
    form_class = RegisterForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('drive:home')

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, f'Welcome, {self.object.username}! Your account was created.')
        return response


class CustomLoginView(LoginView):
    """
    Wraps Django's built-in LoginView so we control the template
    and can keep styling consistent with the rest of the app.
    """
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, f'Welcome back, {form.get_user().username}!')
        return super().form_valid(form)


@login_required
def logout_view(request):
    """
    Django's logout doesn't require a view of its own in modern Django,
    but wrapping it lets us add a message and control the redirect cleanly.
    """
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('accounts:login')


class ProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = ProfileUpdateForm
    template_name = 'accounts/profile.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully.')
        return super().form_valid(form)