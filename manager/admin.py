from django.contrib import admin
from manager.models import *
# Register your models here.

admin.site.register(Queue)
admin.site.register(RestaurantQueue)
admin.site.register(BankQueue)
admin.site.register(Resource)