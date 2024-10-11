from django.shortcuts import render, redirect
from django.views import generic
from queue_manager.models import *
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm


class IndexView(generic.ListView):
    template_name = 'queue_manager/index.html'
    context_object_name = 'queue_list'

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Queue.objects.filter(participant__user=self.request.user)
        else:
            return Queue.objects.none()


