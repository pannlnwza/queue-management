from django.shortcuts import render
from django.views import generic


class MainView(generic.TemplateView):
    template_name = 'queue_manager/index.html'
