from django.urls import path
from . import views_kurir

urlpatterns = [
    path('login/', views_kurir.kurir_login, name='kurir_login'),
    path('logout/', views_kurir.kurir_logout, name='kurir_logout'),
    path('', views_kurir.kurir_dashboard, name='kurir_dashboard'),
    path('transaksi/<int:transaksi_id>/update/', views_kurir.kurir_update_transaksi, name='kurir_update_transaksi'),
]