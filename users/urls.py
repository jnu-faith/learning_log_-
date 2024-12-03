'''为应用程序users定义URL模式'''
from django.urls import path,include

app_name = 'users'
urlpatterns = [
    #包含默认的身份验证URL
    path('',include('django.contrib.auth.urls')),

]