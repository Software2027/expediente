from django.urls import path
from . import views

app_name = 'expedientes'

urlpatterns = [
    path('', views.buscador, name='buscador'),
    path('expediente/<int:pk>/', views.detalle, name='detalle'),
    path('expediente/<int:pk>/marcar/', views.marcar_ubicado, name='marcar_ubicado'),
]
